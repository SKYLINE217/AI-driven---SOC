---
name: soc-triager-cia-triad-access-control
description: Use this skill whenever the user asks about SOC Triager confidentiality/integrity/availability controls specifically framed through the CIA triad, data classification levels, encryption at rest/in transit, graceful-degradation behavior, chaos-testing procedures, or the full subject×object×permission access control matrix and role hierarchy. Trigger this for "what's our data classification for X", "what happens if Redis goes down", "walk me through the access control matrix", or general CIA-triad security-course-style questions applied to SOC Triager. Use `soc-triager-security` alongside this for authentication/RBAC implementation code and the STRIDE threat model — this skill is the CIA-triad framing and the exhaustive permission matrix.
---

# SOC Triager — CIA Triad & Access Control Systems

> Audience: both engineers + security reviewers. Scope: how the MVP implements and enforces Confidentiality, Integrity, and Availability at every layer, plus the complete access control model.

## Why each pillar matters for a SOC platform

| Pillar | Stakes |
|---|---|
| **Confidentiality** | Incident data reveals the organization's attack surface. Playbooks reveal its defenses. Both are extremely sensitive. |
| **Integrity** | Analysts make containment decisions based on AI-generated data. Tampered alerts or manipulated MITRE mappings could cause incorrect (or missed) responses to real attacks. |
| **Availability** | A SOC platform that goes down during an active incident is worse than no platform. Real-time alerting must be resilient. |

## Confidentiality

### Data classification
| Data type | Classification | Notes |
|---|---|---|
| Raw log lines | **Restricted** | May contain credentials, PII, hostnames (`auth.log`, CloudTrail events) |
| Normalized events | **Restricted** | ECS-formatted event records |
| Incident detail | **Confidential** | Attacker IPs, targeted hosts, user accounts, attack timelines |
| Containment playbooks | **Strictly Confidential** | Firewall rules, account operations, network segmentation changes |
| Anomaly scores + features | **Internal** | Reveals detection logic; could help attackers evade |
| MITRE technique mappings | **Internal** | Reveals which TTPs are monitored |
| LLM triage rationale | **Confidential** | Contains interpreted threat intelligence |
| Audit ledger | **Restricted** | Contains actor identities and action history |
| API keys / secrets | **Strictly Confidential** | Anthropic API key, JWT secret, DB passwords |

### Controls
- **Encryption at rest** — Postgres data directory: filesystem-level encryption (dm-crypt/LUKS or encrypted volumes on Railway/Fly.io); Redis: no persistence of sensitive data by default in the sprint config, and any RDB/AOF dump sits on an encrypted volume; Vercel env vars: encrypted at rest by Vercel.
- **Encryption in transit** — Browser→BFF: HTTPS + HSTS; BFF→FastAPI: TLS 1.2+, certificate verified (never `verify=False`); Faust→Redpanda: SASL/SCRAM+TLS in production (plaintext OK on localhost-only Compose); FastAPI→Postgres: SSL mode `require`; FastAPI→Redis: `rediss://` in production.
- **Access control (confidentiality dimension)** — no unauthenticated routes except `/health`; raw log content capped at 500 chars in API responses, full access `senior_analyst`+ only; playbook drafts readable by all roles but approval restricted to `approver`; LLM API key never touches the client bundle, all LLM calls are server-side.
- **Data minimization in LLM calls** — only structured fields (IP, hostname, action, count, duration) go to the Anthropic API. Raw log lines — which may contain passwords, tokens, or PII — are **never** sent to any third-party API.
- **Vercel Deployment Protection** — Preview deployments password-protected when the repo/demo data is sensitive, preventing public access via PR-comment links.

## Integrity

- **Hash-chained audit ledger** — every state-changing action creates a cryptographically linked `incident_ledger` entry: `hash_N = SHA-256(hash_{N-1} || payload_N)`. Properties: append-only (Postgres row-level security, `FOR INSERT` only policy), tamper-evident (modifying/deleting a historical entry breaks the chain — visualized in the Audit Trail tab), non-repudiable (actor identity from JWT recorded with every entry).
- **Input validation** — all API inputs are Pydantic models with strict type/pattern constraints; extra/malformed fields → `422` before reaching business logic.
- **Log content sanitization** — raw log lines sanitized before use in Markdown templates, Mermaid graph definitions, and Ansible playbook variables (IPs/hostnames/ports only, pattern-validated) — prevents an attacker crafting log lines to inject content into reports or playbooks.
- **LLM output integrity** — Claude's output is constrained to a Pydantic-validated schema: `technique_id` must be one of the pre-supplied candidates (prevents hallucinated IDs), `severity` must be an allowed enum value, all strings have max lengths. Validation failure triggers retry; after 2 failures the alert is marked `triage_pending` — never silently accepted with invalid data.
- **MITRE corpus pinning** — the STIX 2.1 Enterprise ATT&CK corpus is pinned to `v15.1` by filename and SHA-256, verified at startup:
```python
def verify_corpus_integrity():
    with open(CORPUS_PATH, 'rb') as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
    if actual_hash != EXPECTED_HASH.split(':')[1]:
        raise RuntimeError("MITRE ATT&CK corpus integrity check failed — possible tampering")
```
- **Dependency integrity** — Python deps pinned with SHA-256 hashes (`pip install --require-hashes`); NPM uses `package-lock.json` + `npm ci`; audits on every PR.
- **Database write controls** — all writes go through SQLAlchemy ORM, no raw SQL interpolation; `incident_ledger` has a row-security policy preventing `UPDATE`/`DELETE`; service accounts get only the minimum DB privileges (e.g. the Faust worker's DB user can only `INSERT` into `normalized_events` and `feature_snapshots`).

## Availability

### Graceful degradation
| Component failure | Degraded behavior | Not affected |
|---|---|---|
| LLM API timeout | Alert stored as `triage_status: pending_manual`; analyst notified | Event ingestion, scoring, alert creation |
| Scoring API down | Faust buffers normalized events in Redpanda (7-day retention); scoring resumes on recovery | Existing incidents, UI, WebSocket |
| Redpanda broker down | Replay producer retries with backoff; Faust reconnects | Existing incidents, UI |
| Redis down | Feature computation falls back to TimescaleDB (slower); WS fan-out degrades to polling | Core incident management |
| Postgres down | API returns `503`; incidents not lost (events still in Redpanda) | Nothing — Postgres is the source of truth |
| Vercel deployment issue | Previous deployment auto-rolled back | N/A |
| FastAPI process crash | `restart: unless-stopped` restarts the container | In-flight requests (<1s downtime) |

### WebSocket resilience
Client reconnects with exponential backoff (1s, 2s, 4s… 30s max, 10 retries); `LiveConnectionPill` shows `reconnecting`; on reconnect, client calls `GET /api/alerts` to refill missed events; `ManualRefresh` button appears after 10 failed reconnects.

### Rate limiting
Vercel Edge Middleware per-IP sliding-window limits protect against both accidental client hammering and deliberate DoS — applied before any request reaches Serverless Functions or the backend.

### Load test targets (Day 5)
| Scenario | Target |
|---|---|
| 1× real-time replay | p95 end-to-end latency < 5 s |
| 5× real-time replay | p95 < 10 s; no event loss |
| 20× real-time replay | Bottleneck identified/documented (Faust consumer lag measured); no silent drops |
| LLM API simulated outage | All alerts reach `triage_pending`; zero silent drops |
| Redis crash + restart | Recovers within 60 s; no data loss from Postgres-persisted events |

### Chaos testing procedure
```bash
# Kill Redpanda mid-stream
docker compose stop redpanda
# Verify: Faust worker logs "connection lost, retrying"; no events silently dropped
docker compose start redpanda
# Verify: consumer lag clears within 30 s

# Simulate LLM API timeout — set ANTHROPIC_API_KEY invalid temporarily
# Verify: alerts appear in DB with triage_status = "pending_manual"
# Restore valid key — verify pending alerts can be re-triaged manually

# Kill FastAPI process
docker compose stop incident-api
# Verify: LiveConnectionPill shows "disconnected" within 5 s
docker compose start incident-api
# Verify: LiveConnectionPill shows "connected" within 35 s (reconnect cycle)
```

## Access control system — full specification

### Subject × object × permission matrix
Subjects: `analyst`, `senior_analyst`, `approver`, `system` (automated pipeline).

| Object | analyst | senior_analyst | approver | system |
|---|---|---|---|---|
| `alerts` — read | ✅ | ✅ | ✅ | ✅ |
| `alerts` — acknowledge / assign to self | ✅ | ✅ | ✅ | — |
| `incidents` — read | ✅ | ✅ | ✅ | ✅ |
| `incidents` — escalate / close | ❌ | ✅ | ✅ | — |
| `incidents` — annotate ledger | ❌ | ✅ | ✅ | ✅ |
| `reports` — read | ✅ | ✅ | ✅ | — |
| `playbook_draft` — read / download | ✅ | ✅ | ✅ | — |
| `playbook` — approve for ops | ❌ | ❌ | ✅ | — |
| `mitre_data` — read | ✅ | ✅ | ✅ | ✅ |
| `ops_metrics` — read | ✅ | ✅ | ✅ | — |
| `audit_ledger` — read | ✅ | ✅ | ✅ | — |
| `audit_ledger` — write | ❌ | ❌ | ❌ | ✅ (system only) |
| `raw_logs_full` — read | ❌ | ✅ (500-char cap lifted) | ✅ | ✅ |
| `scoring_api` — call | ❌ | ❌ | ❌ | ✅ (Faust only) |
| `model_registry` — read | ❌ | ❌ | ❌ | ✅ (scoring API only) |

### Role hierarchy
```
approver → inherits all senior_analyst permissions → inherits all analyst permissions
```
```python
ROLE_HIERARCHY = {
    'analyst': ['analyst'],
    'senior_analyst': ['analyst', 'senior_analyst'],
    'approver': ['analyst', 'senior_analyst', 'approver']
}
def require_role(*allowed_roles: str):
    def checker(claims: dict = Depends(verify_jwt)):
        user_effective_roles = ROLE_HIERARCHY.get(claims.get('role'), [])
        if not any(r in user_effective_roles for r in allowed_roles):
            raise HTTPException(403, "Insufficient role")
        return claims
    return checker
```

### Service-to-service access control
Internal services use a shared `INTERNAL_SERVICE_TOKEN` (separate from user JWTs):

| Caller | Callee | Auth method |
|---|---|---|
| Faust worker | Scoring API | `X-Internal-Auth: <token>` |
| Faust worker | Postgres | DB user `faust_rw` (INSERT only, specific tables) |
| Faust worker | Redis | Redis AUTH password |
| FastAPI | Postgres | DB user `api_rw` (full CRUD on incidents/alerts; INSERT-only on ledger) |
| FastAPI | Redis | Redis AUTH password |
| BFF (Vercel) | FastAPI | `X-Internal-Auth: <token>` + user JWT forwarded for audit logging |

### Containment approval workflow
```
Analyst views playbook (read-only, any role)
  → "Approve for Ops" button
      ├─ Client: RoleGate disables the button for non-approvers (UX only)
      ├─ BFF: requires 'approver' claim → 403 otherwise
      ├─ FastAPI: re-validates 'approver' claim independently → 403 otherwise
      └─ On success: Postgres sets playbook_approved=true + approved_by/at;
                     ledger PLAYBOOK_APPROVED entry with actor + hash chain;
                     green toast to the approver's UI
```
**What "approve" does NOT do:** does not execute any code, scripts, or network changes; does not send commands to any infrastructure; creates only a human-readable authorization record. Actual execution requires a separate out-of-band workflow (copy playbook → run via Ansible Tower or equivalent). This is a **deliberate safety boundary**, not a missing feature.

### Network access control
```
Internet → Vercel CDN (HTTPS only) → React SPA static assets + BFF (/api/*) → FastAPI (8000, HTTPS via Caddy)
All other backend ports bound to 127.0.0.1 (VM loopback only): Redis:6379, Postgres:5432, Redpanda:9092, Prometheus:9090
```
VM firewall (ufw/iptables): allow TCP 22 (SSH, key-based only), 80 (→ redirected to HTTPS), 443 (→ Caddy → FastAPI:8000); deny everything else.

## CIA triad — summary control map

| Layer | Confidentiality | Integrity | Availability |
|---|---|---|---|
| Network | TLS everywhere; internal ports on loopback | TLS cert verification; no MITM | Rate limiting at BFF edge |
| Application (BFF) | JWT validation; role enforcement; no secrets in bundle | Input validation; RBAC blocks unauthorized writes | Edge caching reduces backend load |
| Application (FastAPI) | Independent JWT+role validation; response data minimization | Pydantic validation; parameterized queries; log sanitization | `restart: unless-stopped`; graceful shutdown |
| ML/LLM pipeline | LLM receives structured fields only, never raw logs/PII | Schema-validated LLM output; MITRE corpus integrity check | Graceful degradation to `triage_pending` on LLM failure |
| Database | Encrypted at rest; service-specific DB users, minimum privileges | Append-only ledger with row security; hash-chain integrity | TimescaleDB compression; `pg_dump` backups |
| Streaming | Internal-only Redpanda; SASL/SCRAM in production | Event dedup via event IDs | 7-day retention buffers outages; consumer group auto-rebalancing |
| Secrets | Env vars only, never in code; gitleaks in pre-commit | Hashed deps (`--require-hashes`); CI secret scanning | Vault migration path documented |
| Deployment | Vercel Deployment Protection on previews | CI required-to-merge status checks | Vercel instant rollback; zero-downtime deploys |
