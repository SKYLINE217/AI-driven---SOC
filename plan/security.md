# SOC Triager — Security Architecture & Threat Model

> **Owner:** Both engineers (shared responsibility)
> **Scope:** Authentication, authorization, secrets management, input validation, injection prevention, dependency hygiene, network hardening, and the formal threat model for the MVP.

---

## 1. Security Principles

1. **Defense in depth** — every security control is duplicated at multiple layers (BFF + FastAPI for RBAC; env vars + network isolation for secrets).
2. **Least privilege** — every service, role, and API key has only the permissions it needs.
3. **Human-in-the-loop** — containment playbooks are drafts only; no automated execution path exists.
4. **Auditability** — every state-changing action is recorded in the append-only, hash-chained incident ledger.
5. **Fail safe** — on LLM timeout or broker outage, alerts land in a `pending` state; nothing is silently dropped.
6. **Secure by default** — secrets never touch the codebase; all inputs are validated at the API boundary.

---

## 2. Authentication

### 2.1 JWT Design

- **Algorithm:** HS256 (sprint); RS256 recommended for production (asymmetric; allows BFF and FastAPI to verify without sharing a write key)
- **Expiry:** 1 hour; refresh not implemented in sprint (re-login after expiry)
- **Secret storage:** Vercel Environment Variable `JWT_SECRET` (Preview and Production scoped separately); same secret injected into FastAPI via `JWT_SECRET` env var on the backend VM
- **Payload:**
  ```json
  {
    "sub": "user@example.com",
    "role": "analyst",
    "iat": 1723280000,
    "exp": 1723283600,
    "jti": "<uuid>"    ← unique per token; enables future revocation list
  }
  ```
- `jti` (JWT ID) is stored in Redis with TTL = expiry; revocation is done by deleting the key (not implemented in sprint but the hook is there)

### 2.2 Token Transmission

- Transmitted in `Authorization: Bearer <token>` header only — never in URL query strings for REST endpoints
- WebSocket connection: `?token=<jwt>` in the initial upgrade URL only (unavoidable for browser WS API); the token is validated on connection and the URL is not logged
- `Secure; HttpOnly; SameSite=Strict` cookie is the preferred pattern for production; sprint uses in-memory JS storage (no `localStorage`) to avoid XSS persistence

### 2.3 Validation Chain

```
Browser → BFF (validate JWT signature + expiry + role) → FastAPI (re-validate JWT, independent)
```

FastAPI re-validates because the BFF is a separate service; a compromised BFF cannot escalate privileges to the backend.

---

## 3. Authorization — RBAC

### 3.1 Role Definitions

| Role | Permissions |
|---|---|
| `analyst` | Read all data; acknowledge alerts; assign to self |
| `senior_analyst` | All analyst permissions + escalate incidents + close incidents + annotate ledger |
| `approver` | All senior analyst permissions + approve containment playbooks |

### 3.2 Enforcement Layers

**Layer 1 — Client (UX only):** `RoleGate` component renders action buttons as disabled with tooltips for insufficient roles. This is purely cosmetic — it prevents accidents, not attacks.

**Layer 2 — BFF (pre-flight):** Edge Middleware reads the role claim from the JWT before forwarding the request. Returns `403` immediately for role-gated routes, reducing backend load from unauthorized calls.

**Layer 3 — FastAPI (authoritative):** Every role-gated endpoint has a `require_role` dependency:

```python
from fastapi import Depends, HTTPException

def require_role(*allowed_roles: str):
    def checker(claims: dict = Depends(verify_jwt)):
        if claims["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return claims
    return checker

@router.post("/incidents/{id}/approve")
async def approve_playbook(
    id: str,
    claims: dict = Depends(require_role("approver"))
):
    ...
```

This layer is the real security control. It operates even if the BFF is bypassed by a direct API call.

### 3.3 RBAC Bypass Testing

The test suite (`backend/tests/test_rbac.py`) explicitly tests that:
- An `analyst` JWT calling `POST /api/incidents/:id/approve` receives `403`
- A forged JWT (wrong signature) receives `401`
- An expired JWT receives `401`
- An `approver` JWT calling `POST /api/incidents/:id/approve` receives `200`

Playwright E2E test (`frontend/e2e/rbac.spec.ts`) tests the full UI flow:
- Switch to Analyst role → click Approve button → assert it is disabled
- Switch to Approver role → click Approve button → assert modal appears → confirm → assert success toast

---

## 4. Secrets Management

### 4.1 Sprint Configuration

| Secret | Location | Access |
|---|---|---|
| `ANTHROPIC_API_KEY` | Vercel Env Var (BFF) + backend VM `.env` | BFF (for direct LLM calls if any) + FastAPI/LLM module |
| `JWT_SECRET` | Vercel Env Var + backend VM `.env` | BFF (issue) + FastAPI (verify) |
| `POSTGRES_PASSWORD` | backend VM `.env` only | FastAPI + Faust worker |
| `REDIS_PASSWORD` | backend VM `.env` only | FastAPI + Faust worker |
| `MLFLOW_TRACKING_URI` | backend VM `.env` only | ML training scripts + scoring API |

**Rules enforced in CI:**
- `gitleaks` pre-commit hook scans for secrets before every commit
- GitHub Actions `secret-scan` step runs `truffleHog` on every PR
- `.env` files are in `.gitignore` and a `.gitignore` lint check is in CI

### 4.2 Production Migration Path

HashiCorp Vault replaces `.env` files:
- Vault Agent sidecar injects secrets into the Docker Compose environment at runtime
- Dynamic database credentials: Vault generates short-lived Postgres credentials per service (15-min TTL, auto-rotated)
- `ANTHROPIC_API_KEY` stored in Vault KV v2 with audit logging

---

## 5. Input Validation & Injection Prevention

### 5.1 API Boundary Validation

All FastAPI request bodies are Pydantic models with strict field types. No raw `dict` inputs are accepted:

```python
class StatusUpdateRequest(BaseModel):
    status: Literal["ack", "escalated", "closed"]
    note: Optional[str] = Field(None, max_length=1000, pattern=r'^[\w\s.,!?-]*$')
```

Pydantic's `model_config = {"extra": "forbid"}` rejects any fields not in the schema (prevents parameter pollution).

### 5.2 Log Injection Prevention

**Critical:** attacker-controlled log content (raw log lines) flows through the pipeline into:
- Markdown incident reports
- Mermaid attack graph labels
- Ansible playbook variable values

All three must sanitize before rendering:

```python
import re
import html

def sanitize_log_content(raw: str) -> str:
    """Strip control characters and Markdown/Mermaid injection characters from raw log lines."""
    # Remove ANSI escape codes
    raw = re.sub(r'\x1b\[[0-9;]*m', '', raw)
    # Remove characters that break Mermaid syntax
    raw = re.sub(r'[<>{}"\[\]|;]', '', raw)
    # HTML-escape for Markdown rendering
    return html.escape(raw, quote=True)[:500]  # hard cap at 500 chars

def sanitize_ansible_var(value: str) -> str:
    """Validate Ansible variable values are safe (IPs, hostnames, ports only)."""
    # Only allow values matching expected patterns
    if not re.match(r'^[\w.\-:/]+$', value):
        raise ValueError(f"Unsafe value for Ansible variable: {repr(value)}")
    return value
```

These functions are called in the artifact generation service before any template rendering.

### 5.3 SQL Injection

FastAPI uses SQLAlchemy with parameterized queries throughout. Raw SQL strings with f-strings are banned (enforced by a `bandit` lint rule in CI):

```python
# BANNED — never do this
cursor.execute(f"SELECT * FROM alerts WHERE entity = '{entity}'")

# CORRECT
result = await db.execute(select(Alert).where(Alert.entity == entity))
```

### 5.4 Prompt Injection via Log Content

The LLM triage client never inserts raw log lines directly into the system prompt or user message. Only structured fields (source IP, action, event count, duration) are interpolated:

```python
def build_triage_prompt(event_cluster: list[NormalizedEvent], candidates: list[str]) -> str:
    # Structured fields only — never raw log text
    summary = {
        "source_ip": event_cluster[0].source.ip,  # validated IPv4/IPv6
        "target_host": event_cluster[0].destination.host,  # alphanumeric hostname
        "action": event_cluster[0].event.action,  # enum-validated
        "event_count": len(event_cluster),
        "duration_seconds": (event_cluster[-1].timestamp - event_cluster[0].timestamp).seconds,
        "candidate_techniques": candidates  # from our own rules.yaml, not user input
    }
    return json.dumps(summary)
```

Raw log lines are stored in the database and shown in the UI (with HTML escaping) but are never sent to the LLM.

---

## 6. Network Security

### 6.1 Exposed Surfaces

| Surface | Exposed to | Protection |
|---|---|---|
| Vercel BFF (`/api/*`) | Internet | JWT validation, rate limiting, HTTPS only |
| React SPA | Internet | No secrets in bundle; Vercel HTTPS |
| FastAPI (port 8000) | Internet via reverse proxy | JWT validation (independent of BFF); TLS via Caddy |
| Redpanda (port 9092) | VM internal only | Bound to `127.0.0.1` in production |
| Redis (port 6379) | VM internal only | Bound to `127.0.0.1`; password auth enabled |
| Postgres (port 5432) | VM internal only | Bound to `127.0.0.1`; strong password |
| Prometheus (port 9090) | VM internal only | Not exposed externally |
| Grafana (port 3001) | VM internal only | Not exposed externally (use SSH tunnel to view) |

### 6.2 Rate Limiting

Vercel Edge Middleware applies per-IP rate limits:

```typescript
// frontend/middleware.ts
import { NextRequest, NextResponse } from 'next/server'
import { Ratelimit } from '@upstash/ratelimit'

const ratelimit = new Ratelimit({ limiter: Ratelimit.slidingWindow(100, '1m') })

export async function middleware(req: NextRequest) {
  const ip = req.ip ?? '127.0.0.1'
  const { success } = await ratelimit.limit(ip)
  if (!success) return NextResponse.json({ error: { code: 'RATE_LIMITED' } }, { status: 429 })
}
```

Limits:
- `/api/auth/login`: 10 requests/minute per IP
- `/api/alerts`, `/api/incidents`: 100 requests/minute per IP
- `/api/incidents/:id/approve`: 10 requests/minute per IP (extra conservative)

### 6.3 HTTPS Enforcement

- Vercel enforces HTTPS on all routes; HTTP requests are redirected to HTTPS
- Backend VM: Caddy reverse proxy auto-provisions a Let's Encrypt TLS certificate for the public domain; HTTP → HTTPS redirect enabled
- `Strict-Transport-Security: max-age=63072000; includeSubDomains` header set by Caddy

---

## 7. Dependency Security

### 7.1 Scanning

CI (`.github/workflows/ci.yml`) runs on every PR:

```yaml
- name: Audit Python dependencies
  run: pip-audit --require-hashes -r backend/requirements.txt

- name: Audit NPM dependencies
  run: npm audit --audit-level=high
  working-directory: frontend
```

Critical or high CVEs block the PR merge.

### 7.2 Pinning

- `backend/requirements.txt` — all dependencies pinned to exact versions with SHA-256 hashes (`pip install --require-hashes`)
- `frontend/package-lock.json` — committed and enforced (`npm ci` in CI, never `npm install`)
- MITRE ATT&CK corpus — pinned to `enterprise-attack-v15.1.json` by filename and SHA-256 hash verified at startup

### 7.3 SBOM

Day 5 generates a Software Bill of Materials:
- Python: `pip-licenses --format json > docs/sbom-python.json`
- NPM: `npx license-checker --json > docs/sbom-npm.json`

---

## 8. Threat Model (STRIDE)

### 8.1 Assets

| Asset | Sensitivity |
|---|---|
| Incident data (hosts, IPs, attack patterns) | High — reveals org security posture |
| Containment playbooks (firewall rules, account operations) | Critical — misuse could disrupt operations |
| JWT signing secret | Critical — compromise allows identity spoofing |
| Anthropic API key | High — financial exposure + data exfiltration risk |
| Audit ledger | High — tampering destroys forensic integrity |

### 8.2 STRIDE Analysis

**S — Spoofing**
- *Threat:* Attacker forges a JWT with `role: approver` to approve containment actions
- *Mitigation:* JWT signature verified with HS256 secret; secret stored only in Vercel env vars and backend VM env; never in code
- *Residual risk:* If `JWT_SECRET` is leaked, all sessions are compromised → migrate to RS256 + Vault for production

**T — Tampering**
- *Threat:* Attacker modifies a `pending` alert record to change the MITRE technique or severity before analyst review
- *Mitigation:* All DB writes go through FastAPI with JWT auth; direct DB access requires VM compromise; hash-chained ledger detects post-hoc tampering
- *Threat:* Attacker injects malicious Mermaid/Markdown syntax into log lines to execute XSS via the rendered dashboard
- *Mitigation:* Log content sanitized before template rendering; `react-markdown` renders with `rehype-sanitize` to strip disallowed HTML

**R — Repudiation**
- *Threat:* Analyst denies approving a containment action
- *Mitigation:* Append-only hash-chained ledger records every action with actor identity and timestamp; ledger entries are cryptographically linked so deletion is detectable

**I — Information Disclosure**
- *Threat:* Attacker reads raw log lines (containing internal hostnames, user accounts) from the API
- *Mitigation:* All endpoints require valid JWT; raw log content is capped at 500 chars in the API response; full raw logs are only available to `senior_analyst` and `approver` roles
- *Threat:* Anthropic API key leaked in client bundle
- *Mitigation:* API key stored in Vercel environment variable; never referenced in frontend code; all LLM calls go server-side (backend VM or BFF)

**D — Denial of Service**
- *Threat:* Attacker floods `/api/alerts` with requests to exhaust BFF compute
- *Mitigation:* Per-IP rate limiting on all BFF routes via Vercel Edge Middleware
- *Threat:* Replay producer floods Redpanda with events faster than the pipeline can process, causing consumer lag and memory exhaustion
- *Mitigation:* Faust worker has a configurable `concurrency` limit; Redpanda topic retention caps storage; load test on Day 5 validates the bottleneck is LLM concurrency (bounded by clustering), not the streaming layer

**E — Elevation of Privilege**
- *Threat:* `analyst` role user calls `POST /api/incidents/:id/approve` directly (bypassing UI)
- *Mitigation:* FastAPI `require_role("approver")` dependency returns `403` regardless of how the request is made; documented and tested in `test_rbac.py`

---

## 9. Security Checklist (Day 5)

Run this checklist on Day 5 before the production deploy:

- [ ] `git log --all --oneline | xargs git show | grep -E 'ANTHROPIC|JWT_SECRET|POSTGRES_PASSWORD'` — no secrets in git history
- [ ] `pip-audit` — zero critical/high CVEs in Python deps
- [ ] `npm audit --audit-level=high` — zero high CVEs in frontend deps
- [ ] Verify `.env` is in `.gitignore` and not tracked
- [ ] Confirm Vercel env vars are set for both Preview and Production environments
- [ ] Confirm `Authorization: Bearer` is required on every FastAPI route (no unauthenticated routes except `/health`)
- [ ] Test `POST /api/incidents/:id/approve` with `analyst` JWT → assert `403`
- [ ] Test WebSocket connection with expired JWT → assert connection refused
- [ ] Confirm Redpanda, Redis, Postgres are bound to `127.0.0.1` (not `0.0.0.0`) on the VM
- [ ] Confirm all log content is sanitized before rendering in Markdown/Mermaid/Ansible templates
- [ ] Confirm Vercel Preview URL is password-protected (Vercel Deployment Protection) if the repo is private or contains sensitive demo data
- [ ] Run Playwright RBAC test suite against Production URL — all assertions pass
