# SOC Triager — CIA Triad & Access Control Systems

> **Audience:** Both engineers + security reviewers
> **Scope:** How the SOC Triager MVP implements and enforces Confidentiality, Integrity, and Availability at every layer, and the complete access control model.

---

## 1. Overview

The CIA Triad frames the three fundamental goals of information security. For an AI-driven SOC platform, each pillar carries specific weight:

| Pillar | Why It Matters for a SOC Platform |
|---|---|
| **Confidentiality** | Incident data reveals your organization's attack surface. Playbooks reveal your defenses. Both are extremely sensitive. |
| **Integrity** | Analysts make containment decisions based on AI-generated data. Tampered alerts or manipulated MITRE mappings could cause incorrect (or missed) responses to real attacks. |
| **Availability** | A SOC platform that goes down during an active incident is worse than no platform. Real-time alerting must be resilient. |

---

## 2. Confidentiality

### 2.1 Data Classification

| Data Type | Classification | Examples |
|---|---|---|
| Raw log lines | **Restricted** — may contain credentials, PII, hostnames | `auth.log`, CloudTrail events |
| Normalized events | **Restricted** | ECS-formatted event records |
| Incident detail | **Confidential** | Attacker IPs, targeted hosts, user accounts, attack timelines |
| Containment playbooks | **Strictly Confidential** | Firewall rules, account operations, network segmentation changes |
| Anomaly scores + features | **Internal** | Reveals detection logic; could help attackers evade |
| MITRE technique mappings | **Internal** | Reveals which TTPs are monitored |
| LLM triage rationale | **Confidential** | Contains interpreted threat intelligence |
| Audit ledger | **Restricted** | Contains actor identities and action history |
| API keys / secrets | **Strictly Confidential** | Anthropic API key, JWT secret, DB passwords |

### 2.2 Confidentiality Controls

#### Encryption at Rest
- **Postgres data directory:** filesystem-level encryption on the VM (dm-crypt/LUKS on Linux VMs; encrypted storage volumes on Railway/Fly.io)
- **Redis:** no persistence of sensitive data to disk in sprint configuration; if RDB/AOF enabled, the dump file is stored on an encrypted volume
- **Vercel environment variables:** encrypted at rest by Vercel's infrastructure; never in plaintext in the dashboard API responses

#### Encryption in Transit
- **Browser → BFF (Vercel):** HTTPS enforced; HTTP requests redirected to HTTPS; HSTS header set
- **BFF → FastAPI:** HTTPS over TLS 1.2+ minimum; certificate verified by BFF (no `verify=False`)
- **Faust → Redpanda:** SASL/SCRAM + TLS in production; plaintext acceptable on localhost-only Docker Compose
- **FastAPI → Postgres:** SSL mode `require` enforced in SQLAlchemy connection string
- **FastAPI → Redis:** TLS connection (`rediss://` scheme) in production; plaintext on localhost-only Docker Compose

#### Access Control (Confidentiality Dimension)
- No unauthenticated API routes (except `/health`)
- Raw log content never returned in full via API — maximum 500 character preview, `senior_analyst`+ only
- Playbook drafts readable by all roles but approval action restricted to `approver`
- LLM API key never touches the client bundle — all LLM calls are server-side

#### Data Minimization in LLM Calls
Only structured fields (IP, hostname, action, count, duration) are sent to the Anthropic API. Raw log lines — which may contain passwords, tokens, or PII — are never sent to any third-party API.

#### Vercel Deployment Protection
Preview deployments are password-protected (Vercel Deployment Protection) when the repo contains sensitive demo data, preventing public access to preview URLs shared in PR comments.

---

## 3. Integrity

### 3.1 Integrity Controls

#### Hash-Chained Audit Ledger

Every state-changing action in the system creates an entry in `incident_ledger`, which is cryptographically linked:

```
Entry N:  hash_N = SHA-256(hash_{N-1} || payload_N)
Entry N+1: hash_{N+1} = SHA-256(hash_N || payload_{N+1})
```

Properties:
- **Append-only:** enforced via Postgres row-level security (`FOR INSERT` only policy)
- **Tamper-evident:** modifying or deleting any historical entry breaks the chain; the UI's Audit Trail tab visualizes chain integrity
- **Non-repudiable:** actor identity (from JWT) is recorded with every entry

#### Input Validation

All API inputs are validated by Pydantic models with strict type and pattern constraints. Requests with extra or malformed fields are rejected with `422` before reaching business logic.

#### Log Content Sanitization

Raw log lines (attacker-controlled strings) are sanitized before being used in:
- Markdown templates (prevent Markdown injection)
- Mermaid graph definitions (prevent graph syntax injection)
- Ansible playbook variables (only IPs, hostnames, ports allowed — pattern-validated)

This prevents a malicious actor from injecting content into incident reports or containment playbooks by crafting log lines.

#### LLM Output Integrity

The LLM triage client constrains Claude's output to a Pydantic-validated JSON schema:
- `technique_id` must be one of the pre-provided candidates (prevents hallucinated technique IDs)
- `severity` must be one of `[critical, high, medium, low]`
- All string fields have maximum lengths
- Schema validation failure triggers retry; after 2 failures, the alert is marked `triage_pending` (never silently accepted with invalid data)

#### MITRE Corpus Pinning

The STIX 2.1 Enterprise ATT&CK corpus is pinned to a specific version (`v15.1`) by filename and SHA-256 hash verified at startup:

```python
EXPECTED_HASH = "sha256:abc123..."

def verify_corpus_integrity():
    with open(CORPUS_PATH, 'rb') as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
    if actual_hash != EXPECTED_HASH.split(':')[1]:
        raise RuntimeError("MITRE ATT&CK corpus integrity check failed — possible tampering")
```

#### Dependency Integrity

All Python dependencies pinned with SHA-256 hashes in `requirements.txt` (`pip install --require-hashes`). NPM uses `package-lock.json` with `npm ci` in CI. Dependency audits run on every PR.

#### Database Write Controls

- All database writes go through FastAPI's SQLAlchemy ORM — no raw SQL string interpolation
- `incident_ledger` has a Postgres row-security policy preventing `UPDATE` and `DELETE`
- Service accounts have only the minimum database privileges they need (e.g., the Faust worker's DB user can only `INSERT` into `normalized_events` and `feature_snapshots`)

---

## 4. Availability

### 4.1 Graceful Degradation

The system is designed so that component failures degrade gracefully rather than causing total outages:

| Component Failure | Degraded Behavior | Not Affected |
|---|---|---|
| LLM API timeout | Alert stored as `triage_status: pending_manual`; analyst notified | Event ingestion, scoring, alert creation |
| Scoring API down | Faust worker buffers normalized events in Redpanda (retention 7 days); scoring resumes when API recovers | Existing incidents, UI, WebSocket |
| Redpanda broker down | Replay producer retries with backoff; Faust consumer reconnects | Existing incidents, UI |
| Redis down | Feature computation falls back to TimescaleDB (slower but functional); WebSocket fan-out degrades to polling fallback | Core incident management |
| Postgres down | API returns `503`; incidents not lost (events still in Redpanda) | Nothing — Postgres is the source of truth |
| Vercel deployment | Previous deployment auto-rolled back by Vercel | N/A |
| FastAPI process crash | Docker Compose `restart: unless-stopped` restarts the container | In-flight requests (< 1 s of downtime) |

### 4.2 WebSocket Resilience

Client-side reconnection with exponential backoff (1 s, 2 s, 4 s … 30 s max, 10 retries):
- `LiveConnectionPill` shows `reconnecting` state to analysts during outage
- After reconnection, the client calls `GET /api/alerts` to refill any missed events
- `ManualRefresh` button appears after 10 failed reconnects as a final fallback

### 4.3 Rate Limiting (Availability Protection)

Rate limiting on the BFF protects the backend from:
- Accidental hammering from misbehaving clients
- Deliberate DoS attempts from the internet

The Vercel Edge Middleware applies per-IP sliding window limits before any request reaches the Serverless Functions or the backend.

### 4.4 Load Test Targets (Day 5)

| Scenario | Target |
|---|---|
| 1× real-time event replay | p95 end-to-end latency < 5 s |
| 5× real-time event replay | p95 end-to-end latency < 10 s; no event loss |
| 20× real-time event replay | Bottleneck identified and documented; Faust consumer lag measured; no silent drops |
| LLM API simulated outage | All alerts reach `triage_pending` status; zero silent drops |
| Redis crash and restart | Service recovers within 60 s; no data loss from Postgres-persisted events |

### 4.5 Chaos Testing Procedure (Day 5)

```bash
# Kill Redpanda mid-stream
docker compose stop redpanda
# Verify: Faust worker logs show "connection lost, retrying"
# Verify: No events silently dropped (check normalized_events count before/after)
docker compose start redpanda
# Verify: Consumer lag clears within 30 s

# Simulate LLM API timeout
# Set ANTHROPIC_API_KEY to an invalid value temporarily
# Verify: Alerts appear in DB with triage_status = "pending_manual"
# Restore valid key
# Verify: Pending alerts can be re-triaged manually

# Kill FastAPI process
docker compose stop incident-api
# Verify: LiveConnectionPill shows "disconnected" state in UI within 5 s
docker compose start incident-api
# Verify: LiveConnectionPill shows "connected" within 35 s (reconnect cycle)
```

---

## 5. Access Control System — Full Specification

### 5.1 Subject × Object × Permission Matrix

**Subjects:** `analyst`, `senior_analyst`, `approver`, `system` (automated pipeline)

**Objects and Permissions:**

| Object | analyst | senior_analyst | approver | system |
|---|---|---|---|---|
| `alerts` — read | ✅ | ✅ | ✅ | ✅ |
| `alerts` — acknowledge | ✅ | ✅ | ✅ | — |
| `alerts` — assign to self | ✅ | ✅ | ✅ | — |
| `incidents` — read | ✅ | ✅ | ✅ | ✅ |
| `incidents` — escalate | ❌ | ✅ | ✅ | — |
| `incidents` — close | ❌ | ✅ | ✅ | — |
| `incidents` — annotate ledger | ❌ | ✅ | ✅ | ✅ |
| `reports` — read | ✅ | ✅ | ✅ | — |
| `playbook_draft` — read | ✅ | ✅ | ✅ | — |
| `playbook_draft` — download | ✅ | ✅ | ✅ | — |
| `playbook` — approve for ops | ❌ | ❌ | ✅ | — |
| `mitre_data` — read | ✅ | ✅ | ✅ | ✅ |
| `ops_metrics` — read | ✅ | ✅ | ✅ | — |
| `audit_ledger` — read | ✅ | ✅ | ✅ | — |
| `audit_ledger` — write | ❌ | ❌ | ❌ | ✅ (system only) |
| `raw_logs_full` — read | ❌ | ✅ (500-char cap lifted) | ✅ | ✅ |
| `scoring_api` — call | ❌ | ❌ | ❌ | ✅ (Faust only) |
| `model_registry` — read | ❌ | ❌ | ❌ | ✅ (scoring API only) |

### 5.2 Role Hierarchy

```
approver
  └── inherits all senior_analyst permissions
        └── inherits all analyst permissions
```

Implemented in FastAPI's `require_role` dependency:

```python
ROLE_HIERARCHY = {
    'analyst':         ['analyst'],
    'senior_analyst':  ['analyst', 'senior_analyst'],
    'approver':        ['analyst', 'senior_analyst', 'approver']
}

def require_role(*allowed_roles: str):
    def checker(claims: dict = Depends(verify_jwt)):
        user_role = claims.get('role')
        user_effective_roles = ROLE_HIERARCHY.get(user_role, [])
        if not any(r in user_effective_roles for r in allowed_roles):
            raise HTTPException(403, "Insufficient role")
        return claims
    return checker
```

### 5.3 Service-to-Service Access Control

Internal services authenticate to each other using a shared `INTERNAL_SERVICE_TOKEN` (separate from user JWTs):

| Caller | Callee | Auth Method |
|---|---|---|
| Faust worker | Scoring API | `X-Internal-Auth: <token>` |
| Faust worker | Postgres | DB user: `faust_rw` (INSERT on specific tables only) |
| Faust worker | Redis | Redis AUTH password |
| FastAPI | Postgres | DB user: `api_rw` (full CRUD on incidents, alerts; INSERT-only on ledger) |
| FastAPI | Redis | Redis AUTH password |
| BFF (Vercel) | FastAPI | `X-Internal-Auth: <token>` + user JWT forwarded for audit logging |

Each service's DB user has only the minimum Postgres privileges required — principle of least privilege enforced at the database level.

### 5.4 Containment Approval Workflow

The approval workflow is the most security-sensitive flow in the system:

```
Analyst views playbook (read-only, any role)
    │
    └──▶ "Approve for Ops" button
              │
              ├── Client: RoleGate renders button as disabled for analyst/senior_analyst
              │          (UX layer only)
              │
              ├── BFF: requires 'approver' role claim in JWT → 403 if not
              │
              ├── FastAPI: re-validates 'approver' role claim independently → 403 if not
              │
              └── On success:
                   ├── Postgres: incident.playbook_approved = true, approved_by, approved_at
                   ├── Ledger: PLAYBOOK_APPROVED entry with actor + hash chain
                   └── Toast: green confirmation to approver's UI
```

**What "approve" does NOT do:**
- Does not execute any code, scripts, or network changes
- Does not send commands to any infrastructure
- Creates a human-readable record that a designated approver reviewed and authorized the playbook
- The actual execution requires a separate out-of-band workflow (copy playbook → run via Ansible Tower or equivalent)

This boundary is a deliberate safety design, not a missing feature.

### 5.5 Network Access Control

Beyond application-level RBAC, network-level controls restrict access:

```
Internet
  │
  ├──▶ Vercel CDN (HTTPS only)
  │       └──▶ React SPA static assets
  │       └──▶ BFF Serverless Functions (/api/*)
  │                 └──▶ FastAPI (8000, HTTPS via Caddy reverse proxy)
  │
  └── All other backend ports: bound to 127.0.0.1 (VM loopback only)
       Redis:6379, Postgres:5432, Redpanda:9092, Prometheus:9090
```

**VM firewall rules (ufw / iptables):**
```
ALLOW  in  tcp 22   (SSH — key-based only, password auth disabled)
ALLOW  in  tcp 80   (HTTP → redirected to HTTPS by Caddy)
ALLOW  in  tcp 443  (HTTPS → Caddy → FastAPI:8000)
DENY   in  all      (everything else)
```

---

## 6. CIA Triad — Summary Control Map

| Layer | Confidentiality | Integrity | Availability |
|---|---|---|---|
| **Network** | TLS everywhere; internal ports bound to loopback | TLS certificate verification; no MITM | Rate limiting at BFF edge |
| **Application (BFF)** | JWT validation; role enforcement; no secrets in client bundle | Input validation; RBAC prevents unauthorized writes | Edge caching reduces backend load |
| **Application (FastAPI)** | Independent JWT + role validation; data minimization in API responses | Pydantic validation; parameterized queries; log sanitization | `restart: unless-stopped`; graceful shutdown |
| **ML/LLM Pipeline** | LLM receives structured fields only (no raw logs/PII) | Schema-validated LLM output; MITRE corpus integrity check | Graceful degradation to `triage_pending` on LLM failure |
| **Database** | Encrypted at rest; service-specific DB users with minimum privileges | Append-only ledger with row security; hash-chain integrity | TimescaleDB automatic compression; backups via `pg_dump` |
| **Streaming** | Internal-only Redpanda; SASL/SCRAM in production | Event deduplication via event IDs | 7-day retention buffers outages; consumer group auto-rebalancing |
| **Secrets** | Env vars only; never in code; gitleaks in pre-commit | Hashed deps with `--require-hashes`; secret scanning in CI | Vault migration path documented for production |
| **Deployment** | Vercel Deployment Protection on previews | CI required-to-merge status checks | Vercel instant rollback; zero-downtime deploys |
