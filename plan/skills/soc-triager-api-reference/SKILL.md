---
name: soc-triager-api-reference
description: Use this skill whenever the user needs the exact SOC Triager HTTP/WebSocket API contract — endpoint paths, query parameters, request/response JSON shapes, role-gated permissions per endpoint, the error schema, or BFF responsibilities. Trigger this for any question about `GET /api/alerts`, `POST /api/incidents/:id/approve`, the `/ws/alerts` WebSocket protocol, HTTP status codes, or "what does the response for X look like". This is the authoritative wire-format contract between the React frontend, the Vercel BFF, and the FastAPI backend for the SOC Triager project — prefer this over inferring shapes from component code.
---

# SOC Triager — API Reference

> **Base URL (backend):** `https://<vm-host>/` (HTTPS via reverse proxy)
> **Base URL (BFF):** `https://<vercel-app>.vercel.app/api/` — all client traffic goes here; the BFF proxies to the backend.
> **Auth:** every endpoint requires a short-lived JWT in `Authorization: Bearer <token>`. The BFF issues JWTs and validates them before forwarding.

## Authentication

### `POST /api/auth/login` (mock/demo login)
Request: `{ "username": "analyst@example.com", "role": "analyst" }`
Response: `{ "access_token": "<JWT>", "role": "analyst", "expires_in": 3600 }`
Roles: `analyst`, `senior_analyst`, `approver`.
JWT payload: `{ "sub": "<email>", "role": "<role>", "iat": <ts>, "exp": <ts> }` — signed HS256, secret in Vercel env vars, never in the client bundle. In production this endpoint is replaced by an OIDC redirect.

### Role-gated endpoints
| Endpoint | Analyst | Senior Analyst | Approver |
|---|---|---|---|
| `GET /api/alerts` | ✅ | ✅ | ✅ |
| `GET /api/incidents` | ✅ | ✅ | ✅ |
| `POST /api/incidents/:id/status` | Ack only | Ack + Escalate + Close | All |
| `POST /api/incidents/:id/approve` | ❌ 403 | ❌ 403 | ✅ |
| `GET /api/incidents/:id/playbook` | ✅ | ✅ | ✅ |
| `GET /api/metrics` | ✅ | ✅ | ✅ |

## Alerts

### `GET /api/alerts`
Query params: `page` (default 1), `limit` (default 50, max 200), `severity` (CSV, e.g. `critical,high,medium`), `status` (CSV: `new,ack,escalated,closed`), `technique` (CSV of technique IDs), `entity` (free-text host/user/IP match), `from`/`to` (ISO 8601), `sort` (default `timestamp:desc`).

Response:
```json
{
  "total": 1842, "page": 1, "limit": 50,
  "alerts": [{
    "id": "a-uuid", "incident_id": "i-uuid", "severity": "high",
    "timestamp": "2026-08-10T09:14:22.104Z",
    "entity": { "host": "prod-db-03", "user": "svc-backup", "source_ip": "203.0.113.44" },
    "technique_id": "T1110.001", "technique_name": "Brute Force: Password Guessing",
    "tactic": "Credential Access", "anomaly_score": 0.87,
    "score_history": [0.12, 0.14, 0.11, 0.89, 0.87],
    "status": "new", "assignee": null, "created_at": "2026-08-10T09:14:25.000Z"
  }]
}
```

### `POST /api/alerts/bulk-ack`
Request: `{ "alert_ids": ["a-uuid-1", "a-uuid-2"] }` → `200 OK` with updated alert objects.

### `POST /api/alerts/bulk-assign`
Same request shape; assigns to the authenticated user.

## Incidents

### `GET /api/incidents`
Same filters as `/api/alerts`. Response: `{ "total": 43, "page": 1, "incidents": [{ id, title, severity, status, technique_id, tactic, alert_count, entity_count, created_at, updated_at, assignee }] }`.

### `GET /api/incidents/:id`
Full detail: `{ id, title, severity, status, technique_id, technique_name, tactic, confidence, llm_rationale, recommended_action, entities: [{role, ip, geo_country} | {role, host, user}], alerts: [ids], created_at, updated_at }`.

### `GET /api/incidents/:id/timeline`
`{ "events": [{ timestamp, action, source_ip, destination_host, user, raw_preview }] }` — ordered by timestamp.

### `GET /api/incidents/:id/ledger`
Append-only audit trail: `{ "entries": [{ seq, hash, prev_hash, timestamp, action, actor, payload }] }`.

### `POST /api/incidents/:id/status`
Request: `{ "status": "escalated", "note": "Forwarding to IR team" }`. `close` and `escalate` return `403` for `analyst`. `200 OK` with updated incident object; a ledger entry is appended automatically.

### `POST /api/incidents/:id/approve`
`403` for `analyst` and `senior_analyst`. Request: `{ "note": "Reviewed and confirmed safe to execute" }`. Response: `{ "approved": true, "approved_by": "...", "approved_at": "...", "ledger_entry": { "seq": 8, "hash": "..." } }`.

### `GET /api/incidents/:id/report.md`
Generated Markdown incident report, `text/markdown`.

### `GET /api/incidents/:id/graph.mmd`
Mermaid-syntax attack graph, `text/plain`.

### `GET /api/incidents/:id/playbook`
Containment playbook, `text/yaml` (Ansible) or `text/plain`, with `Content-Disposition: attachment; filename="playbook-<incident-id>.yml"`.

## MITRE ATT&CK

### `GET /api/mitre/technique/:technique_id`
From the pinned STIX bundle, no external call: `{ id, name, tactic, description, detection, mitigations: [...], data_sources: [...], url }`.

### `GET /api/navigator/layer.json`
MITRE ATT&CK Navigator-compatible layer JSON reflecting technique frequency across current-week incidents. Consumed directly by `/navigator`.

## Metrics

### `GET /api/metrics`
```json
{
  "throughput": { "current_eps": 1240, "history_1h": [{ "ts": "...", "eps": 1180 }] },
  "alert_volume": { "last_24h": 384, "trend_7d": [{ "date": "2026-08-04", "count": 312 }] },
  "anomaly_score_distribution": { "bins": [0.0, 0.1, ...], "counts": [12400, 8300, ...] },
  "llm_cost": { "cost_per_1000_flagged_usd": 0.42, "trend_7d": [{ "date": "...", "cost": 0.38 }] },
  "pipeline_latency": { "p50_ms": 312, "p95_ms": 1840, "history_1h": [{ "ts": "...", "p50": 290, "p95": 1720 }] }
}
```
The BFF fetches this from Prometheus and reshapes it for Recharts.

## Internal scoring endpoint (not exposed through BFF)

### `POST /score` (Scoring API — internal only, called by Faust)
Request: `{ entity_key, features: { event_count_1m, event_count_5m, failed_auth_ratio, distinct_dest_ports, dest_ip_fanout, bytes_transferred, tod_zscore, geo_velocity_kmh }, event_id }`.
Response: `{ score, threshold, is_anomaly, top_features: [{ name, contribution }], model_version, latency_ms }`.

## WebSocket — live alert feed

`WS /ws/alerts`, connected via the BFF proxy (`wss://<vercel-app>.vercel.app/api/ws/alerts`). JWT passed as query param on connect: `?token=<jwt>`.

Message types (server → client):
- `{ "type": "new_alert", "alert": { /* same shape as GET /api/alerts item */ } }`
- `{ "type": "incident_updated", "incident_id": "...", "status": "escalated" }`
- `{ "type": "heartbeat", "ts": "..." }` — sent every 30s; client must `pong` within 10s or the server closes the connection.

**Client reconnection:** exponential backoff starting at 1s, max 30s, up to 10 retries before showing `Disconnected`.

## Error schema

```json
{ "error": { "code": "FORBIDDEN", "message": "Only users with the 'approver' role can approve containment playbooks.", "request_id": "req-uuid" } }
```

| Code | Meaning |
|---|---|
| `400` | Invalid request body or parameters |
| `401` | Missing or invalid JWT |
| `403` | Valid JWT but insufficient role |
| `404` | Resource not found |
| `422` | Pydantic validation error (request body shape) |
| `429` | Rate limit exceeded (BFF edge middleware) |
| `500` | Internal server error (logged with `request_id`) |
| `503` | Backend service temporarily unavailable (BFF can't reach FastAPI) |

## BFF responsibilities (Vercel layer)

Before forwarding to FastAPI, the BFF (`frontend/api/*`): (1) validates JWT signature + expiry (`401` if invalid), (2) extracts the role claim, (3) blocks role-gated requests with `403` before forwarding if role is insufficient (defense-in-depth — FastAPI checks again), (4) applies per-IP rate limits via Vercel Edge Middleware, (5) caches MITRE technique descriptions and Navigator layers at the edge for 60s, (6) injects the backend's internal base URL from `BACKEND_API_URL` (never exposed to the client bundle).

## OpenAPI docs (backend-network only, not exposed in production)

Swagger UI `http://localhost:8000/docs`, ReDoc `http://localhost:8000/redoc`, JSON schema `http://localhost:8000/openapi.json`.
