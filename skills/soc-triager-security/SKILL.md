---
name: soc-triager-security
description: Use this skill whenever the user asks about SOC Triager security controls — JWT/authentication design, RBAC enforcement layers, secrets management, input validation and injection prevention (log injection, SQL injection, prompt injection), network security and rate limiting, dependency scanning, the STRIDE threat model, or the Day-5 security checklist. Trigger this for any "is this secure", "how do we prevent X injection", "what happens if a secret leaks", or pre-launch security review question about SOC Triager. Use `soc-triager-cia-triad-access-control` alongside this for the confidentiality/integrity/availability framing and the full access-control permission matrix.
---

# SOC Triager — Security Architecture & Threat Model

> Owner: both engineers (shared responsibility). Scope: authentication, authorization, secrets, input validation/injection prevention, dependency hygiene, network hardening, and the formal threat model.

## Security principles

1. **Defense in depth** — every control is duplicated at multiple layers (BFF + FastAPI for RBAC; env vars + network isolation for secrets).
2. **Least privilege** — every service, role, and API key has only the permissions it needs.
3. **Human-in-the-loop** — containment playbooks are drafts only; no automated execution path exists.
4. **Auditability** — every state-changing action is recorded in the append-only, hash-chained incident ledger.
5. **Fail safe** — on LLM timeout or broker outage, alerts land in a `pending` state; nothing is silently dropped.
6. **Secure by default** — secrets never touch the codebase; all inputs validated at the API boundary.

## Authentication

**JWT design:** HS256 for the sprint (RS256 recommended for production — asymmetric, lets BFF and FastAPI verify without sharing a write key). Expiry: 1 hour, no refresh in-sprint (re-login after expiry). Secret storage: Vercel env var `JWT_SECRET` (Preview and Production scoped separately), same value injected into FastAPI on the backend VM. Payload includes a `jti` (JWT ID) stored in Redis with TTL = expiry — the revocation hook exists but isn't wired up in the sprint.

**Token transmission:** `Authorization: Bearer <token>` header for REST — never in URL query strings. WebSocket connection uses `?token=<jwt>` on the upgrade URL (unavoidable for the browser WS API); token validated on connect, URL not logged. Production pattern is `Secure; HttpOnly; SameSite=Strict` cookies; the sprint uses in-memory JS storage (no `localStorage`) to avoid XSS persistence.

**Validation chain:** `Browser → BFF (validate signature+expiry+role) → FastAPI (re-validate JWT, independently)`. FastAPI re-validates because it's a separate service — a compromised BFF cannot escalate privileges to the backend.

## Authorization — RBAC

| Role | Permissions |
|---|---|
| `analyst` | Read all data; acknowledge alerts; assign to self |
| `senior_analyst` | All analyst + escalate incidents + close incidents + annotate ledger |
| `approver` | All senior_analyst + approve containment playbooks |

**Three enforcement layers:**
1. **Client (UX only)** — `RoleGate` renders disabled buttons with tooltips. Cosmetic; prevents accidents, not attacks.
2. **BFF (pre-flight)** — Edge Middleware reads the role claim and returns `403` before forwarding, reducing backend load from unauthorized calls.
3. **FastAPI (authoritative)** — every role-gated endpoint has a `require_role` dependency; this is the real control, and it operates even if the BFF is bypassed by a direct API call:
```python
def require_role(*allowed_roles: str):
    def checker(claims: dict = Depends(verify_jwt)):
        if claims["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return claims
    return checker
```

**RBAC bypass testing** (`backend/tests/test_rbac.py`): analyst JWT calling approve → `403`; forged-signature JWT → `401`; expired JWT → `401`; approver JWT calling approve → `200`. Playwright (`frontend/e2e/rbac.spec.ts`) exercises the full UI flow for both a disabled and an enabled Approve button.

## Secrets management

| Secret | Location | Access |
|---|---|---|
| `ANTHROPIC_API_KEY` | Vercel env var (BFF) + backend VM `.env` | BFF + FastAPI/LLM module |
| `JWT_SECRET` | Vercel env var + backend VM `.env` | BFF (issue) + FastAPI (verify) |
| `POSTGRES_PASSWORD` | backend VM `.env` only | FastAPI + Faust worker |
| `REDIS_PASSWORD` | backend VM `.env` only | FastAPI + Faust worker |
| `MLFLOW_TRACKING_URI` | backend VM `.env` only | ML training scripts + scoring API |

CI rules: `gitleaks` pre-commit hook scans before every commit; GitHub Actions `secret-scan` runs `truffleHog` on every PR; `.env` is gitignored with a lint check in CI.

**Production migration:** HashiCorp Vault replaces `.env` — Vault Agent sidecar injects secrets at runtime, dynamic Postgres credentials (15-min TTL, auto-rotated), `ANTHROPIC_API_KEY` in Vault KV v2 with audit logging.

## Input validation & injection prevention

**API boundary:** all FastAPI request bodies are strict-typed Pydantic models, `model_config = {"extra": "forbid"}` rejects unexpected fields (prevents parameter pollution). Example: `status: Literal["ack","escalated","closed"]`, `note: Optional[str] = Field(None, max_length=1000, pattern=r'^[\w\s.,!?-]*$')`.

**Log injection prevention** — attacker-controlled raw log content flows into Markdown reports, Mermaid graph labels, and Ansible playbook variables. All three sanitize first:
```python
def sanitize_log_content(raw: str) -> str:
    raw = re.sub(r'\x1b\[[0-9;]*m', '', raw)          # strip ANSI escapes
    raw = re.sub(r'[<>{}"\[\]|;]', '', raw)             # strip Mermaid-breaking chars
    return html.escape(raw, quote=True)[:500]            # HTML-escape, hard cap 500 chars

def sanitize_ansible_var(value: str) -> str:
    if not re.match(r'^[\w.\-:/]+$', value):
        raise ValueError(f"Unsafe value for Ansible variable: {repr(value)}")
    return value
```
These are called in the artifact generation service before every template render — never skip this for "trusted" input, since the whole point is that log content is attacker-controlled.

**SQL injection** — SQLAlchemy with parameterized queries throughout; raw f-string SQL is banned and enforced by a `bandit` lint rule in CI:
```python
# BANNED
cursor.execute(f"SELECT * FROM alerts WHERE entity = '{entity}'")
# CORRECT
result = await db.execute(select(Alert).where(Alert.entity == entity))
```

**Prompt injection via log content** — the LLM triage client never puts raw log lines into the system or user prompt. Only structured, pre-validated fields go in (source IP, action, event count, duration):
```python
def build_triage_prompt(event_cluster, candidates):
    summary = {
        "source_ip": event_cluster[0].source.ip,          # validated IPv4/IPv6
        "target_host": event_cluster[0].destination.host, # alphanumeric hostname
        "action": event_cluster[0].event.action,           # enum-validated
        "event_count": len(event_cluster),
        "duration_seconds": (event_cluster[-1].timestamp - event_cluster[0].timestamp).seconds,
        "candidate_techniques": candidates                 # from our own rules.yaml, not user input
    }
    return json.dumps(summary)
```
Raw log lines are stored in the DB and shown in the UI (HTML-escaped) but are **never sent to the LLM**.

## Network security

| Surface | Exposed to | Protection |
|---|---|---|
| Vercel BFF (`/api/*`) | Internet | JWT validation, rate limiting, HTTPS only |
| React SPA | Internet | No secrets in bundle; Vercel HTTPS |
| FastAPI (8000) | Internet via reverse proxy | Independent JWT validation; TLS via Caddy |
| Redpanda (9092) | VM internal only | Bound to `127.0.0.1` in production |
| Redis (6379) | VM internal only | Bound to `127.0.0.1`; password auth |
| Postgres (5432) | VM internal only | Bound to `127.0.0.1`; strong password |
| Prometheus (9090) | VM internal only | Not exposed externally |
| Grafana (3001) | VM internal only | SSH tunnel to view |

**Rate limiting** (Vercel Edge Middleware, per-IP sliding window): `/api/auth/login` 10/min, `/api/alerts` and `/api/incidents` 100/min, `/api/incidents/:id/approve` 10/min (extra conservative).

**HTTPS enforcement** — Vercel redirects HTTP → HTTPS on all routes; backend VM uses Caddy for auto-provisioned Let's Encrypt certs and HTTP→HTTPS redirect; `Strict-Transport-Security: max-age=63072000; includeSubDomains` set by Caddy.

## Dependency security

CI runs `pip-audit --require-hashes -r backend/requirements.txt` and `npm audit --audit-level=high` on every PR — critical/high CVEs block merge. Pinning: `requirements.txt` uses exact versions + SHA-256 hashes (`pip install --require-hashes`); `package-lock.json` committed and enforced via `npm ci` (never `npm install`); MITRE corpus pinned by filename + SHA-256 verified at startup. Day 5 generates an SBOM (`pip-licenses`, `license-checker`).

## Threat model (STRIDE)

**Assets:** incident data (High), containment playbooks (Critical), JWT signing secret (Critical), Anthropic API key (High), audit ledger (High).

| Threat category | Example threat | Mitigation |
|---|---|---|
| **Spoofing** | Forged JWT with `role: approver` | HS256 signature verification; secret only in env vars, never in code. Residual risk: leaked `JWT_SECRET` compromises all sessions → migrate to RS256 + Vault |
| **Tampering** | Direct DB write changes a pending alert's technique/severity | All writes go through FastAPI + JWT; direct DB access needs VM compromise; hash-chained ledger detects post-hoc tampering |
| **Tampering** | Malicious Mermaid/Markdown in log lines → XSS | Log content sanitized pre-render; `react-markdown` + `rehype-sanitize` strips disallowed HTML |
| **Repudiation** | Analyst denies approving a containment action | Append-only hash-chained ledger with actor identity + timestamp; deletion is chain-detectable |
| **Info Disclosure** | Reading raw log lines (internal hostnames/accounts) via the API | JWT required everywhere; raw log content capped at 500 chars; full logs only for `senior_analyst`+ |
| **Info Disclosure** | Anthropic API key leaked in client bundle | Key only in Vercel env vars, never referenced client-side; all LLM calls server-side |
| **DoS** | Flooding `/api/alerts` to exhaust BFF compute | Per-IP rate limiting via Vercel Edge Middleware |
| **DoS** | Replay producer flooding Redpanda faster than the pipeline can process | Faust worker concurrency limit; topic retention caps storage; Day-5 load test confirms LLM concurrency (not streaming) is the bottleneck |
| **Elevation of Privilege** | Analyst calls `POST /api/incidents/:id/approve` directly, bypassing the UI | `require_role("approver")` dependency returns `403` regardless of call path; tested in `test_rbac.py` |

## Day-5 security checklist

- [ ] `git log --all | xargs git show | grep -E 'ANTHROPIC|JWT_SECRET|POSTGRES_PASSWORD'` — no secrets in git history
- [ ] `pip-audit` zero critical/high CVEs
- [ ] `npm audit --audit-level=high` zero high CVEs
- [ ] `.env` is gitignored and untracked
- [ ] Vercel env vars set for both Preview and Production
- [ ] Every FastAPI route requires `Authorization: Bearer` except `/health`
- [ ] `POST /api/incidents/:id/approve` with an `analyst` JWT → `403`
- [ ] WebSocket connect with expired JWT → connection refused
- [ ] Redpanda/Redis/Postgres bound to `127.0.0.1` (not `0.0.0.0`) on the VM
- [ ] All log content sanitized before Markdown/Mermaid/Ansible rendering
- [ ] Vercel Preview URL password-protected (Deployment Protection) if repo/data is sensitive
- [ ] Full Playwright RBAC suite passes against Production URL
