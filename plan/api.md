# SOC Triager — API Reference

> **Audience:** Both engineers; Engineer B consumes these endpoints from the BFF and React app; Engineer A implements the FastAPI backend.
> **Base URL (backend):** `https://<vm-host>/` (HTTPS via reverse proxy)
> **Base URL (BFF):** `https://<vercel-app>.vercel.app/api/` (all client traffic goes here; BFF proxies to backend)
> **Auth:** All endpoints require a valid short-lived JWT in `Authorization: Bearer <token>`. The BFF issues JWTs and validates them before forwarding.

---

## 1. Authentication & Authorization

### 1.1 Mock Login (Demo)

```
POST /api/auth/login
```

**Request body:**
```json
{ "username": "analyst@example.com", "role": "analyst" }
```

**Response:**
```json
{
  "access_token": "<JWT>",
  "role": "analyst",
  "expires_in": 3600
}
```

Roles: `analyst`, `senior_analyst`, `approver`.

JWT payload:
```json
{
  "sub": "analyst@example.com",
  "role": "analyst",
  "iat": 1723280000,
  "exp": 1723283600
}
```

JWT is signed with an HS256 secret stored in Vercel environment variables (never in the client bundle). In production, this endpoint is replaced by an OIDC provider redirect.

### 1.2 Role-Gated Endpoints

| Endpoint | Analyst | Senior Analyst | Approver |
|---|---|---|---|
| `GET /api/alerts` | ✅ | ✅ | ✅ |
| `GET /api/incidents` | ✅ | ✅ | ✅ |
| `POST /api/incidents/:id/status` | Ack only | Ack + Escalate + Close | All |
| `POST /api/incidents/:id/approve` | ❌ 403 | ❌ 403 | ✅ |
| `GET /api/incidents/:id/playbook` | ✅ | ✅ | ✅ |
| `GET /api/metrics` | ✅ | ✅ | ✅ |

---

## 2. Alerts

### `GET /api/alerts`

Retrieve a paginated, filtered list of alerts.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `limit` | int | 50 | Rows per page (max 200) |
| `severity` | string (CSV) | — | Filter by severity: `critical,high,medium` |
| `status` | string (CSV) | — | Filter by status: `new,ack,escalated,closed` |
| `technique` | string (CSV) | — | Filter by technique IDs: `T1110,T1046` |
| `entity` | string | — | Free-text match on host, user, or IP |
| `from` | ISO 8601 | — | Start of time range |
| `to` | ISO 8601 | — | End of time range |
| `sort` | string | `timestamp:desc` | Sort field and direction |

**Response:**
```json
{
  "total": 1842,
  "page": 1,
  "limit": 50,
  "alerts": [
    {
      "id": "a-uuid-here",
      "incident_id": "i-uuid-here",
      "severity": "high",
      "timestamp": "2026-08-10T09:14:22.104Z",
      "entity": {
        "host": "prod-db-03",
        "user": "svc-backup",
        "source_ip": "203.0.113.44"
      },
      "technique_id": "T1110.001",
      "technique_name": "Brute Force: Password Guessing",
      "tactic": "Credential Access",
      "anomaly_score": 0.87,
      "score_history": [0.12, 0.14, 0.11, 0.89, 0.87],
      "status": "new",
      "assignee": null,
      "created_at": "2026-08-10T09:14:25.000Z"
    }
  ]
}
```

### `POST /api/alerts/bulk-ack`

Acknowledge multiple alerts.

**Request body:**
```json
{ "alert_ids": ["a-uuid-1", "a-uuid-2"] }
```

**Response:** `200 OK` with updated alert objects.

### `POST /api/alerts/bulk-assign`

Assign multiple alerts to the authenticated user.

**Request body:**
```json
{ "alert_ids": ["a-uuid-1", "a-uuid-2"] }
```

---

## 3. Incidents

### `GET /api/incidents`

Retrieve paginated incident list. Same filter parameters as `/api/alerts`.

**Response:**
```json
{
  "total": 43,
  "page": 1,
  "incidents": [
    {
      "id": "i-uuid-here",
      "title": "Credential Access via Brute Force: Password Guessing — prod-db-03",
      "severity": "high",
      "status": "new",
      "technique_id": "T1110.001",
      "tactic": "Credential Access",
      "alert_count": 17,
      "entity_count": 3,
      "created_at": "2026-08-10T09:14:25.000Z",
      "updated_at": "2026-08-10T09:20:11.000Z",
      "assignee": null
    }
  ]
}
```

### `GET /api/incidents/:id`

Full incident detail.

**Response:**
```json
{
  "id": "i-uuid-here",
  "title": "...",
  "severity": "high",
  "status": "new",
  "technique_id": "T1110.001",
  "technique_name": "Brute Force: Password Guessing",
  "tactic": "Credential Access",
  "confidence": 0.87,
  "llm_rationale": "17 failed SSH authentication attempts from 203.0.113.44...",
  "recommended_action": "Block source IP at edge firewall; force credential rotation...",
  "entities": [
    { "role": "attacker", "ip": "203.0.113.44", "geo_country": "RU" },
    { "role": "victim", "host": "prod-db-03", "user": "svc-backup" }
  ],
  "alerts": ["a-uuid-1", "a-uuid-2"],
  "created_at": "...",
  "updated_at": "..."
}
```

### `GET /api/incidents/:id/timeline`

Timeline of events for this incident, ordered by timestamp.

**Response:**
```json
{
  "events": [
    {
      "timestamp": "2026-08-10T09:12:00Z",
      "action": "ssh_login_failed",
      "source_ip": "203.0.113.44",
      "destination_host": "prod-db-03",
      "user": "root",
      "raw_preview": "Aug 10 09:12:00 prod-db-03 sshd[1234]: Failed password for root from 203.0.113.44..."
    }
  ]
}
```

### `GET /api/incidents/:id/ledger`

Append-only audit trail for this incident.

**Response:**
```json
{
  "entries": [
    {
      "seq": 7,
      "hash": "a3f9d2c1...",
      "prev_hash": "8bc01422...",
      "timestamp": "2026-08-10T09:20:11Z",
      "action": "PLAYBOOK_APPROVED",
      "actor": "approver@example.com",
      "payload": { "playbook_version": "1.2", "approved_at": "..." }
    }
  ]
}
```

### `POST /api/incidents/:id/status`

Update incident status.

**Request body:**
```json
{ "status": "escalated", "note": "Forwarding to IR team" }
```

**Role enforcement:** `close` and `escalate` actions return `403` for the `analyst` role.

**Response:** `200 OK` with updated incident object. A ledger entry is appended automatically.

### `POST /api/incidents/:id/approve`

Approve the containment playbook for ops execution.

**Role enforcement:** Returns `403` for `analyst` and `senior_analyst` roles.

**Request body:**
```json
{ "note": "Reviewed and confirmed safe to execute" }
```

**Response:**
```json
{
  "approved": true,
  "approved_by": "approver@example.com",
  "approved_at": "2026-08-10T09:20:11Z",
  "ledger_entry": { "seq": 8, "hash": "..." }
}
```

### `GET /api/incidents/:id/report.md`

Returns the generated Markdown incident report as `text/markdown`.

### `GET /api/incidents/:id/graph.mmd`

Returns the Mermaid-syntax attack graph as `text/plain`.

### `GET /api/incidents/:id/playbook`

Returns the generated containment playbook as `text/yaml` (Ansible) or `text/plain` (firewall rules), depending on the template used.

Response includes header: `Content-Disposition: attachment; filename="playbook-<incident-id>.yml"`

---

## 4. MITRE ATT&CK

### `GET /api/mitre/technique/:technique_id`

Returns official ATT&CK technique detail from the pinned STIX bundle (no external network call — loaded at startup).

**Response:**
```json
{
  "id": "T1110.001",
  "name": "Brute Force: Password Guessing",
  "tactic": "Credential Access",
  "description": "Adversaries with no prior knowledge of legitimate credentials...",
  "detection": "Monitor authentication logs for large numbers of failed attempts...",
  "mitigations": ["M1036", "M1032"],
  "data_sources": ["Authentication logs"],
  "url": "https://attack.mitre.org/techniques/T1110/001/"
}
```

### `GET /api/navigator/layer.json`

Returns a MITRE ATT&CK Navigator-compatible layer JSON reflecting technique frequency across all current-week incidents. Used directly by the `/navigator` React page.

---

## 5. Metrics

### `GET /api/metrics`

Returns summarized operational metrics for the `/ops` dashboard page. The BFF fetches this from Prometheus and formats it for Recharts.

**Response:**
```json
{
  "throughput": {
    "current_eps": 1240,
    "history_1h": [{ "ts": "...", "eps": 1180 }, ...]
  },
  "alert_volume": {
    "last_24h": 384,
    "trend_7d": [{ "date": "2026-08-04", "count": 312 }, ...]
  },
  "anomaly_score_distribution": {
    "bins": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    "counts": [12400, 8300, 4200, 1800, 820, 340, 180, 92, 48, 29, 12]
  },
  "llm_cost": {
    "cost_per_1000_flagged_usd": 0.42,
    "trend_7d": [{ "date": "2026-08-04", "cost": 0.38 }, ...]
  },
  "pipeline_latency": {
    "p50_ms": 312,
    "p95_ms": 1840,
    "history_1h": [{ "ts": "...", "p50": 290, "p95": 1720 }, ...]
  }
}
```

---

## 6. Internal Scoring Endpoint

### `POST /score` (Scoring API, internal — not exposed through BFF)

Called by the Faust stream processor. Not reachable from the internet.

**Request:**
```json
{
  "entity_key": "prod-db-03:svc-backup:203.0.113.44",
  "features": {
    "event_count_1m": 17,
    "event_count_5m": 23,
    "failed_auth_ratio": 1.0,
    "distinct_dest_ports": 1,
    "dest_ip_fanout": 1,
    "bytes_transferred": 4200,
    "tod_zscore": 2.1,
    "geo_velocity_kmh": 0
  },
  "event_id": "e-uuid-here"
}
```

**Response:**
```json
{
  "score": 0.87,
  "threshold": 0.72,
  "is_anomaly": true,
  "top_features": [
    { "name": "failed_auth_ratio", "contribution": 0.41 },
    { "name": "event_count_1m", "contribution": 0.28 },
    { "name": "tod_zscore", "contribution": 0.18 }
  ],
  "model_version": "if_v3_ae_v2_ensemble",
  "latency_ms": 3.2
}
```

---

## 7. WebSocket — Live Alert Feed

### `WS /ws/alerts`

Connect via the BFF proxy (`wss://<vercel-app>.vercel.app/api/ws/alerts`). JWT must be sent as a query parameter on connection: `?token=<jwt>`.

**Message format (server → client):**
```json
{
  "type": "new_alert",
  "alert": { /* same shape as GET /api/alerts item */ }
}
```

**Other message types:**

```json
{ "type": "incident_updated", "incident_id": "...", "status": "escalated" }
{ "type": "heartbeat", "ts": "2026-08-10T09:14:22Z" }
```

Heartbeat is sent every 30 s. Client must send a `pong` within 10 s or the server closes the connection (triggers `LiveConnectionPill` reconnect logic).

**Client reconnection:** exponential backoff starting at 1 s, max 30 s, up to 10 retries before showing `Disconnected` state.

---

## 8. Error Schema

All error responses follow a consistent structure:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Only users with the 'approver' role can approve containment playbooks.",
    "request_id": "req-uuid-here"
  }
}
```

**HTTP status codes used:**

| Code | Meaning |
|---|---|
| `400` | Invalid request body or parameters |
| `401` | Missing or invalid JWT |
| `403` | Valid JWT but insufficient role |
| `404` | Resource not found |
| `422` | Pydantic validation error (request body shape) |
| `429` | Rate limit exceeded (BFF edge middleware) |
| `500` | Internal server error (logged with `request_id`) |
| `503` | Backend service temporarily unavailable (BFF fails to reach FastAPI) |

---

## 9. BFF Responsibilities (Vercel Layer)

The BFF (`frontend/api/*` Vercel Serverless Functions) does the following before forwarding to FastAPI:

1. **JWT validation** — verifies signature and expiry; returns `401` if invalid
2. **Role claim extraction** — reads `role` from JWT payload
3. **Role-based request blocking** — for role-gated endpoints, returns `403` before forwarding if role is insufficient (defense-in-depth; FastAPI also checks)
4. **Rate limiting** — Vercel Edge Middleware applies per-IP limits on public routes
5. **Response caching** — MITRE technique descriptions and Navigator layers are cached at the edge for 60 s (low-churn, high-read data)
6. **Backend URL injection** — the backend's internal base URL is read from `BACKEND_API_URL` Vercel environment variable; never exposed to the client bundle

---

## 10. OpenAPI Documentation

The FastAPI backend auto-generates OpenAPI docs at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **JSON schema:** `http://localhost:8000/openapi.json`

The BFF does not expose these externally in production; they are only available on the backend VM network.
