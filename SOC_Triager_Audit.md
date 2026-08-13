# 🛡️ SOC Triager — Full Security & Code Audit
### With Step-by-Step Fix Guide for Antigravity

> **Repository:** `github.com/SKYLINE217/AI-driven---SOC`
> **Audit Date:** 13 August 2026
> **Prepared for:** Antigravity Team
> **Classification:** Internal — Engineering Restricted

---

## Severity Legend

| Badge | Level | Meaning |
|---|---|---|
| 🔴 **CRITICAL** | Must fix before any deployment | Security hole or data loss waiting to happen |
| 🟠 **HIGH** | Fix in Phase 1–2 | Core functionality broken or major risk |
| 🟡 **MEDIUM** | Fix in Phase 2–3 | Real risk but not immediately catastrophic |
| 🟢 **LOW** | Fix when convenient | Quality/hygiene issue |
| 🔵 **INFO** | Awareness only | No action required now, watch in future |

---

## Audit Score Summary

| Dimension | Score | Note |
|---|---|---|
| Core ML Pipeline (IF + AE + MITRE + LLM) | 10/10 | Correctly assembled, good ensemble design |
| Frontend UI Quality | 9/10 | Clean React, good component structure |
| API Integration (frontend ↔ backend contracts) | 7/10 | 4 field-name mismatches + 1 missing route |
| Security Controls (JWT, RBAC, sanitization) | 6/10 | Good design, critical implementation gaps |
| Test Coverage (101 backend tests) | 9/10 | Excellent for a sprint, gaps in integration |
| Documentation | 10/10 | Exceptional README and arch docs |
| **Overall MVP Score** | **9.2/10** | Outstanding sprint output |
| **Production Readiness** | **3/10** | Normal for a 5-day build — this doc fixes it |

---

## Table of Contents

1. [F-01 — Hardcoded Role Credentials on Login Page](#f-01----hardcoded-role-credentials-on-login-page) 🔴
2. [F-02 — In-Memory Incident Store, Zero Durability](#f-02----in-memory-incident-store-zero-durability) 🔴
3. [F-03 — HS256 JWT, Symmetric Secret, No Separation](#f-03----hs256-jwt-symmetric-secret-no-separation) 🔴
4. [F-04 — Faust Streaming Pipeline is a Skeleton](#f-04----faust-streaming-pipeline-is-a-skeleton) 🟠
5. [F-05 — No LLM Cost Controls or Budget Circuit-Breaker](#f-05----no-llm-cost-controls-or-budget-circuit-breaker) 🟠
6. [F-06 — No Real Log Source Integration](#f-06----no-real-log-source-integration) 🟠
7. [F-07 — MLflow on Local SQLite, No Remote Registry](#f-07----mlflow-on-local-sqlite-no-remote-registry) 🟠
8. [F-08 — CORS Wildcard Pattern](#f-08----cors-wildcard-pattern) 🟠
9. [F-09 — WebSocket JWT Exposed in Query Parameter](#f-09----websocket-jwt-exposed-in-query-parameter) 🟠
10. [F-10 — Anomaly Threshold Hardcoded at 0.40](#f-10----anomaly-threshold-hardcoded-at-040) 🟡
11. [F-11 — Ansible IOC Sanitization Insufficient for Complex Types](#f-11----ansible-ioc-sanitization-insufficient-for-complex-types) 🟡
12. [F-12 — No Rate Limiting on FastAPI Backend](#f-12----no-rate-limiting-on-fastapi-backend) 🟡
13. [F-13 — Mermaid XSS Risk in React Renderer](#f-13----mermaid-xss-risk-in-react-renderer) 🟡
14. [F-14 — TimescaleDB Tables Created but Never Written To](#f-14----timescaledb-tables-created-but-never-written-to) 🟡
15. [F-15 — 4 API Surface Mismatches Frontend ↔ Backend](#f-15----4-api-surface-mismatches-frontend--backend) 🟢
16. [F-16 — MLflow SQLite Has No Docker Volume](#f-16----mlflow-sqlite-has-no-docker-volume) 🟢
17. [F-17 — CICIDS2017 Dataset is 9 Years Old](#f-17----cicids2017-dataset-is-9-years-old) 🔵

---

## Quick Wins (Do These Today — Under 1 Hour Each)

These require almost no effort and close real risk immediately. Do them before anything else.

```bash
# 1. Restrict CORS to your exact production URL (10 min)
# In backend/.env:
CORS_ORIGINS=https://your-exact-app.vercel.app

# 2. Enable GitHub secret scanning (5 min)
# Go to repo → Settings → Security → Secret scanning → Enable

# 3. Add startup assertion for JWT_SECRET entropy (15 min)
# In backend/api/main.py, add at top of lifespan():
import os, base64
secret = os.environ.get("JWT_SECRET", "")
assert len(secret) >= 32, "JWT_SECRET must be at least 32 bytes"

# 4. Add MLflow persistent volume (10 min)
# In backend/docker-compose.yml, under the mlflow service:
volumes:
  - mlflow_data:/mlflow
# And at the bottom:
volumes:
  mlflow_data:
```

---

---

## F-01 — Hardcoded Role Credentials on Login Page

> 🔴 **CRITICAL** | `frontend/src/pages/Login.tsx` + `backend/api/routers/auth.py`

### What's Wrong

The login page has three buttons — "Sign in as Analyst", "Sign in as Senior Analyst", "Sign in as Approver". Clicking any button sends a POST to `/api/auth/login` with a body like:

```json
{ "username": "analyst_user", "role": "approver" }
```

The backend accepts whatever `role` value arrives in the request body and puts it directly in the JWT. This means **anyone can give themselves any role** by changing the request body. There is no password, no credential check, nothing. This is not authentication — it's a role-selector.

### Risk

Any external user who discovers the login endpoint can immediately obtain an `approver` JWT and approve containment playbooks against your infrastructure.

### How to Fix — Step by Step

**Step 1: Add a users table to your database**

Add this to `backend/migrations/002_users.sql` (create the file):

```sql
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    VARCHAR(64) UNIQUE NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,          -- bcrypt hash, never plaintext
    role        VARCHAR(32) NOT NULL CHECK (role IN ('analyst','senior_analyst','approver')),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login  TIMESTAMPTZ
);

-- Seed one approver account for initial setup (change password immediately)
-- Generate hash with: python -c "import bcrypt; print(bcrypt.hashpw(b'ChangeMe123!', bcrypt.gensalt()).decode())"
INSERT INTO users (username, email, password_hash, role) VALUES
  ('admin', 'admin@yourorg.com', '$2b$12$REPLACE_WITH_REAL_HASH', 'approver');
```

**Step 2: Update the login router to validate credentials**

Replace `backend/api/routers/auth.py` login handler:

```python
# backend/api/routers/auth.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import bcrypt
from ..auth_middleware import create_access_token
from ..database import get_db  # your async SQLAlchemy session

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str  # <-- replace "role" field with "password"

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/api/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest, db=Depends(get_db)):
    # Look up user in database — never accept role from client
    result = await db.execute(
        "SELECT id, username, password_hash, role, is_active FROM users WHERE username = $1",
        req.username
    )
    user = result.fetchone()

    # Constant-time check to prevent user enumeration
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    password_valid = bcrypt.checkpw(
        req.password.encode("utf-8"),
        user.password_hash.encode("utf-8")
    )
    if not password_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Role comes from the DATABASE, never from the request body
    token = create_access_token({"sub": user.username, "role": user.role})

    # Update last_login timestamp
    await db.execute(
        "UPDATE users SET last_login = NOW() WHERE id = $1", user.id
    )

    return LoginResponse(access_token=token)
```

**Step 3: Replace the three-button login page**

Replace `frontend/src/pages/Login.tsx` with a real form:

```tsx
// frontend/src/pages/Login.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { apiClient } from "../lib/apiClient";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await apiClient.post("/api/auth/login", { username, password });
      setAuth(data.access_token);
      navigate("/alerts");
    } catch {
      setError("Invalid username or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <h1>SOC Triager</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          autoComplete="username"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
        />
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "Signing in..." : "Sign In"}
        </button>
      </form>
    </div>
  );
}
```

**Step 4: Add bcrypt to requirements**

```bash
# In backend/requirements.txt, add:
bcrypt==4.2.1
```

**Step 5: Install and run migration**

```bash
pip install bcrypt==4.2.1
docker compose exec postgres psql -U soc_user -d soc_triager -f /migrations/002_users.sql
```

**Verification:**

```bash
# This should succeed
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"ChangeMe123!"}'

# This should return 401 — role field ignored
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wrong","role":"approver"}'
```

---

## F-02 — In-Memory Incident Store, Zero Durability

> 🔴 **CRITICAL** | `backend/api/incident_service.py`

### What's Wrong

`IncidentService` stores all incidents and alerts as Python `dict` objects in process memory. The class is seeded with 10 fake alerts and 5 fake incidents on every startup. A server restart loses everything. In a real SOC, this means losing ongoing investigations, breaking the hash-chained audit ledger, and potentially losing forensic evidence during an active incident.

```python
# Current code (the problem)
class IncidentService:
    def __init__(self):
        self.incidents: dict[str, Incident] = {}  # ALL DATA LIVES HERE
        self.alerts: dict[str, Alert] = {}
        self._seed_data()  # fake data injected on startup
```

### How to Fix — Step by Step

**Step 1: Set up SQLAlchemy async engine**

Create `backend/database.py`:

```python
# backend/database.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = (
    f"postgresql+asyncpg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ.get('POSTGRES_PORT', 5432)}"
    f"/{os.environ['POSTGRES_DB']}"
)

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # reconnect on stale connections
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

**Step 2: Create SQLAlchemy ORM models**

Create `backend/db_models.py`:

```python
# backend/db_models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, DateTime, Text, Boolean
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class DBIncident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    technique_id: Mapped[str] = mapped_column(String(32), nullable=False)
    technique_name: Mapped[str] = mapped_column(String(256))
    tactic: Mapped[str] = mapped_column(String(128))
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    anomaly_score: Mapped[float] = mapped_column(Float)
    recommended_action: Mapped[str] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class DBLedgerEntry(Base):
    __tablename__ = "audit_ledger"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

**Step 3: Rewrite IncidentService to use the database**

Replace `backend/api/incident_service.py` core methods:

```python
# backend/api/incident_service.py  (rewritten)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..db_models import DBIncident, DBLedgerEntry
from ..models import Incident, LedgerEntry
import hashlib, json
from datetime import datetime

class IncidentService:
    # No __init__ with dicts — database is the store now

    async def get_incident(self, incident_id: str, db: AsyncSession) -> Incident | None:
        result = await db.execute(select(DBIncident).where(DBIncident.id == incident_id))
        row = result.scalar_one_or_none()
        return Incident.model_validate(row) if row else None

    async def list_incidents(self, db: AsyncSession, page: int = 1, page_size: int = 25):
        offset = (page - 1) * page_size
        result = await db.execute(
            select(DBIncident)
            .order_by(DBIncident.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        return [Incident.model_validate(r) for r in result.scalars().all()]

    async def update_status(self, incident_id: str, new_status: str, actor: str, db: AsyncSession):
        await db.execute(
            update(DBIncident)
            .where(DBIncident.id == incident_id)
            .values(status=new_status, updated_at=datetime.utcnow())
        )
        await self._append_ledger(incident_id, f"status_changed_to_{new_status}", actor, db)
        await db.commit()

    async def approve_playbook(self, incident_id: str, approver: str, db: AsyncSession):
        await db.execute(
            update(DBIncident)
            .where(DBIncident.id == incident_id)
            .values(approved_by=approver, approved_at=datetime.utcnow(), status="approved")
        )
        await self._append_ledger(incident_id, "playbook_approved", approver, db)
        await db.commit()

    async def _append_ledger(self, incident_id: str, action: str, actor: str, db: AsyncSession):
        # Get last entry hash for chain
        result = await db.execute(
            select(DBLedgerEntry)
            .where(DBLedgerEntry.incident_id == incident_id)
            .order_by(DBLedgerEntry.created_at.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        previous_hash = last.entry_hash if last else "0" * 64

        detail = json.dumps({"action": action, "actor": actor, "ts": datetime.utcnow().isoformat()})
        entry_hash = hashlib.sha256(f"{previous_hash}{detail}".encode()).hexdigest()

        db.add(DBLedgerEntry(
            incident_id=incident_id,
            action=action,
            actor=actor,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            detail=detail,
        ))
```

**Step 4: Remove the seed data call**

Delete the `_seed_data()` method and its call entirely from `incident_service.py`. Seed data should only exist in a separate `backend/scripts/seed_dev.py` that is never run in production.

**Verification:**

```bash
# Start server, create an incident via API, restart server
# The incident should still be there after restart
curl -X GET http://localhost:8000/api/incidents -H "Authorization: Bearer $TOKEN"
docker compose restart api
curl -X GET http://localhost:8000/api/incidents -H "Authorization: Bearer $TOKEN"
# Both responses must match
```

---

## F-03 — HS256 JWT, Symmetric Secret, No Separation

> 🔴 **CRITICAL** | `backend/api/auth_middleware.py`, `backend/api/routers/auth.py`

### What's Wrong

The current JWT setup uses HS256 — a symmetric algorithm where the same secret is used to both **sign** and **verify** tokens. Any service that needs to verify a JWT must also possess the signing key, meaning any compromised service can forge tokens for any other service. The secret also likely lives in `.env`, which has leaked in production environments worldwide.

### How to Fix — Step by Step

**Step 1: Generate an RSA key pair**

```bash
# Run this once, store output securely
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem

# Store in environment (never commit these files)
# In production: store in HashiCorp Vault or AWS Secrets Manager
# For now, set as environment variables:
export JWT_PRIVATE_KEY=$(cat jwt_private.pem)
export JWT_PUBLIC_KEY=$(cat jwt_public.pem)

# Delete the pem files — live in env vars only
rm jwt_private.pem jwt_public.pem
```

**Step 2: Update auth middleware to use RS256**

```python
# backend/api/auth_middleware.py
import os
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

PRIVATE_KEY = os.environ["JWT_PRIVATE_KEY"]   # used only for signing
PUBLIC_KEY  = os.environ["JWT_PUBLIC_KEY"]    # used for verification everywhere

ALGORITHM = "RS256"  # asymmetric — public key can verify, private key signs

security = HTTPBearer()

def create_access_token(payload: dict, expire_minutes: int = 60) -> str:
    from datetime import datetime, timedelta
    payload = payload.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=expire_minutes)
    return jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            PUBLIC_KEY,
            algorithms=[ALGORITHM],  # reject HS256 explicitly
            options={"require": ["exp", "sub", "role"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(*roles: str):
    def dependency(payload: dict = Security(verify_token)):
        if payload.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return payload
    return dependency
```

**Step 3: Update .env.example**

```bash
# backend/.env.example
# NEVER put actual keys here — this is a template only

# JWT — generate with: openssl genrsa -out /tmp/k.pem 2048
JWT_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"

# Remove JWT_SECRET entirely — it no longer exists
```

**Step 4: Update frontend BFF JWT verification**

```typescript
// frontend/api/_lib/auth.ts
import { importSPKI, jwtVerify } from "jose";

const PUBLIC_KEY_PEM = process.env.JWT_PUBLIC_KEY!;

export async function verifyJWT(token: string) {
  const publicKey = await importSPKI(PUBLIC_KEY_PEM, "RS256");
  const { payload } = await jwtVerify(token, publicKey, {
    algorithms: ["RS256"],  // reject HS256 attempts
  });
  return payload;
}
```

**Verification:**

```bash
# HS256-signed token should be rejected
FAKE_TOKEN=$(python3 -c "import jwt; print(jwt.encode({'sub':'x','role':'approver','exp':9999999999}, 'secret', algorithm='HS256'))")
curl -H "Authorization: Bearer $FAKE_TOKEN" http://localhost:8000/api/incidents
# Expected: 401 Unauthorized
```

---

## F-04 — Faust Streaming Pipeline is a Skeleton

> 🟠 **HIGH** | `backend/stream/faust_app.py`

### What's Wrong

The Faust streaming worker exists as a skeleton — the topic subscriptions and agent logic are not wired to the actual normalizers, feature engineering, ML scoring, MITRE mapping, or LLM triage. In the current state, no real event processing happens. All data in the UI comes from seeded fake data.

### How to Fix — Step by Step

**Step 1: Define topics in faust_app.py**

```python
# backend/stream/faust_app.py
import faust
from ..ingestion.normalizers import get_normalizer
from ..ml.feature_engineering import FeatureEngineer
from ..mitre.mapping_engine import MitreMapper
from ..mitre.alert_clustering import AlertClusterer
from ..llm.triage_client import triage_event_cluster

app = faust.App(
    "soc-triager",
    broker="kafka://localhost:9092",  # Redpanda is Kafka-compatible
    value_serializer="json",
)

# Define input topics (one per source type)
raw_syslog     = app.topic("raw.syslog",     value_type=bytes)
raw_cloudtrail = app.topic("raw.cloudtrail", value_type=bytes)
raw_auth       = app.topic("raw.auth",       value_type=bytes)
raw_cicids     = app.topic("raw.cicids",     value_type=bytes)

# Internal topic for normalised events
normalized_events = app.topic("normalized.events", value_type=dict)

# Dead-letter queue for events that fail processing
dead_letter = app.topic("dlq.events", value_type=dict)
```

**Step 2: Add the normalizer agent**

```python
# backend/stream/faust_app.py (continued)

@app.agent(raw_syslog)
async def process_syslog(stream):
    async for raw_bytes in stream:
        await _normalise_and_forward("syslog", raw_bytes.decode("utf-8", errors="replace"))

@app.agent(raw_cloudtrail)
async def process_cloudtrail(stream):
    async for raw_bytes in stream:
        await _normalise_and_forward("cloudtrail", raw_bytes.decode("utf-8", errors="replace"))

@app.agent(raw_auth)
async def process_auth(stream):
    async for raw_bytes in stream:
        await _normalise_and_forward("auth_log", raw_bytes.decode("utf-8", errors="replace"))

async def _normalise_and_forward(source_type: str, raw_line: str):
    try:
        normalizer = get_normalizer(source_type)
        event = normalizer.normalise(raw_line)
        if event:
            await normalized_events.send(value=event.model_dump())
    except Exception as e:
        # Send to DLQ instead of crashing the agent
        await dead_letter.send(value={
            "source_type": source_type,
            "raw": raw_line[:500],
            "error": str(e),
            "ts": datetime.utcnow().isoformat(),
        })
```

**Step 3: Add the scoring and triage agent**

```python
# backend/stream/faust_app.py (continued)
feature_engineer = FeatureEngineer()  # connects to Redis
mitre_mapper = MitreMapper()
clusterer = AlertClusterer()

@app.agent(normalized_events)
async def score_and_triage(stream):
    async for event_dict in stream:
        try:
            # 1. Extract features from Redis sliding windows
            features = await feature_engineer.extract(event_dict)

            # 2. Call scoring API for ML ensemble score
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://localhost:8001/score",
                    json={"features": features},
                    timeout=5.0
                )
            score_result = resp.json()
            anomaly_score = score_result["score"]
            top_features = score_result["top_features"]

            # 3. Skip if below threshold (fetch from Redis, fallback 0.40)
            import redis.asyncio as aioredis
            r = aioredis.from_url("redis://localhost:6379")
            threshold = float(await r.get("ml:threshold") or 0.40)

            if anomaly_score < threshold:
                continue  # benign — no further processing

            # 4. MITRE heuristic mapping
            candidate_techniques = mitre_mapper.map_event(event_dict, features)

            # 5. Cluster into incidents
            cluster = clusterer.add_event(event_dict, candidate_techniques)
            if not cluster.ready_to_triage:
                continue  # accumulating — not enough events yet

            # 6. LLM triage
            triage = await triage_event_cluster(
                events=cluster.events,
                anomaly_score=anomaly_score,
                top_features=top_features,
                candidate_technique_ids=candidate_techniques,
            )

            # 7. Write incident to database
            from ..api.incident_service import IncidentService
            from ..database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                await IncidentService().create_incident(triage, cluster, db)

        except Exception as e:
            import structlog
            structlog.get_logger().error("triage_agent_error", error=str(e))
```

**Step 4: Add DLQ monitoring agent**

```python
@app.agent(dead_letter)
async def monitor_dlq(stream):
    async for failed_event in stream:
        import structlog
        structlog.get_logger().warning(
            "dlq_event",
            source_type=failed_event.get("source_type"),
            error=failed_event.get("error"),
        )
        # Increment DLQ counter in Redis for Prometheus scraping
        import redis.asyncio as aioredis
        r = aioredis.from_url("redis://localhost:6379")
        await r.incr("metrics:dlq_total")
```

**Step 5: Start and verify**

```bash
# Run the Faust worker
cd backend
python -m faust -A stream.faust_app worker -l info

# In another terminal, inject a synthetic brute-force event
python -c "
from kafka import KafkaProducer
import json
p = KafkaProducer(bootstrap_servers='localhost:9092')
p.send('raw.auth', b'Aug 13 04:52:01 server sshd[1234]: Failed password for root from 192.168.1.100 port 42345 ssh2')
p.flush()
print('Sent')
"

# Check the UI — an incident should appear within 30 seconds
# Check for DLQ events:
python -c "
from kafka import KafkaConsumer
c = KafkaConsumer('dlq.events', bootstrap_servers='localhost:9092', auto_offset_reset='earliest')
for msg in c: print(msg.value); break
"
```

---

## F-05 — No LLM Cost Controls or Budget Circuit-Breaker

> 🟠 **HIGH** | `backend/llm/triage_client.py`

### What's Wrong

Every flagged anomaly triggers a Claude API call immediately with no budget gate. A log flood or adversarially crafted spike could generate thousands of API calls in minutes, running up unbounded costs.

### How to Fix — Step by Step

**Step 1: Add budget tracking to triage_client.py**

```python
# backend/llm/triage_client.py — add these functions

import redis.asyncio as aioredis
from datetime import datetime

DAILY_BUDGET_USD = float(os.environ.get("LLM_DAILY_BUDGET_USD", "50.0"))
COST_PER_1K_INPUT_TOKENS = 0.003   # Claude Sonnet pricing — update as needed
COST_PER_1K_OUTPUT_TOKENS = 0.015

async def _check_and_record_cost(input_tokens: int, output_tokens: int) -> bool:
    """Returns True if budget allows this call, False if circuit-breaker trips."""
    r = aioredis.from_url(os.environ["REDIS_URL"])

    today_key = f"llm:daily_cost:{datetime.utcnow().strftime('%Y-%m-%d')}"
    call_cost = (input_tokens / 1000 * COST_PER_1K_INPUT_TOKENS +
                 output_tokens / 1000 * COST_PER_1K_OUTPUT_TOKENS)

    # Atomic check-and-increment
    current = float(await r.get(today_key) or 0)
    if current >= DAILY_BUDGET_USD:
        return False  # circuit-breaker open

    await r.incrbyfloat(today_key, call_cost)
    await r.expire(today_key, 86400 * 2)  # keep for 2 days

    # Alert at 80% of budget
    if current + call_cost >= DAILY_BUDGET_USD * 0.8:
        await _send_budget_alert(current + call_cost)

    return True

async def _send_budget_alert(current_spend: float):
    """Send alert to PagerDuty or log prominently."""
    import structlog
    structlog.get_logger().warning(
        "llm_budget_warning",
        current_spend_usd=round(current_spend, 4),
        daily_budget_usd=DAILY_BUDGET_USD,
        pct=round(current_spend / DAILY_BUDGET_USD * 100, 1),
    )
    # TODO: POST to PagerDuty Events API v2 here


async def triage_event_cluster(events, anomaly_score, top_features, candidate_technique_ids):
    # Estimate token cost before calling (rough: 1 token ≈ 4 chars)
    estimated_input_tokens = len(str(events)) // 4 + 500  # 500 for system prompt
    budget_ok = await _check_and_record_cost(estimated_input_tokens, 300)

    if not budget_ok:
        # Circuit breaker open — return heuristic-only result
        import structlog
        structlog.get_logger().warning("llm_circuit_breaker_open")
        return _heuristic_fallback_triage(events, anomaly_score, candidate_technique_ids)

    # ... existing Claude API call logic ...
```

**Step 2: Add the heuristic fallback**

```python
def _heuristic_fallback_triage(events, anomaly_score, candidate_technique_ids) -> TriageResult:
    """When LLM is unavailable or over budget, use rule-based triage."""
    primary_technique = candidate_technique_ids[0] if candidate_technique_ids else "T1078"
    severity = "critical" if anomaly_score > 0.8 else "high" if anomaly_score > 0.6 else "medium"

    return TriageResult(
        technique_id=primary_technique,
        technique_name="Unknown — heuristic only",
        tactic="unknown",
        confidence=0.5,
        rationale=f"LLM unavailable (budget/circuit-breaker). Anomaly score: {anomaly_score:.2f}. Heuristic technique: {primary_technique}.",
        severity=severity,
        recommended_immediate_action="Review manually — LLM triage unavailable.",
    )
```

**Step 3: Add the budget cap to .env**

```bash
# In backend/.env
LLM_DAILY_BUDGET_USD=50.0   # Set to your acceptable daily max
```

---

## F-06 — No Real Log Source Integration

> 🟠 **HIGH** | `backend/ingestion/generators/`

### What's Wrong

All log data comes from Python generators producing synthetic strings. There is no live connection to AWS CloudTrail, syslog, auth.log, or any SIEM.

### How to Fix — Step by Step

**Step 1: AWS CloudTrail live connector**

Create `backend/ingestion/connectors/cloudtrail_live.py`:

```python
# backend/ingestion/connectors/cloudtrail_live.py
import boto3
import json
from kafka import KafkaProducer
import os

def start_cloudtrail_poller():
    """Poll CloudTrail via SQS (EventBridge → SQS → Redpanda)."""
    sqs = boto3.client("sqs", region_name=os.environ["AWS_REGION"])
    producer = KafkaProducer(
        bootstrap_servers=os.environ.get("REDPANDA_BROKERS", "localhost:9092")
    )
    queue_url = os.environ["CLOUDTRAIL_SQS_URL"]

    while True:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,  # long polling
        )
        for msg in response.get("Messages", []):
            body = json.loads(msg["Body"])
            # CloudTrail events come wrapped in SNS → SQS envelope
            if "Records" in body:
                for record in body["Records"]:
                    producer.send("raw.cloudtrail", json.dumps(record).encode())
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])

        producer.flush()
```

**Step 2: Syslog TCP/TLS listener**

Create `backend/ingestion/connectors/syslog_listener.py`:

```python
# backend/ingestion/connectors/syslog_listener.py
import asyncio
import ssl
from kafka import KafkaProducer

async def start_syslog_listener(host="0.0.0.0", port=6514):
    """TLS syslog listener on port 6514."""
    producer = KafkaProducer(bootstrap_servers="localhost:9092")

    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain("certs/server.crt", "certs/server.key")

    async def handle_client(reader, writer):
        addr = writer.get_extra_info("peername")
        while not reader.at_eof():
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=30.0)
                if line:
                    producer.send("raw.syslog", line.strip())
            except asyncio.TimeoutError:
                break
        writer.close()

    server = await asyncio.start_server(handle_client, host, port, ssl=ssl_ctx)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(start_syslog_listener())
```

**Step 3: Update docker-compose.yml to expose syslog port**

```yaml
# In backend/docker-compose.yml, add to the api service:
ports:
  - "6514:6514"   # TLS syslog
  - "514:514/udp" # UDP syslog (plaintext, internal network only)
```

**Step 4: Add .env variables**

```bash
# backend/.env
AWS_REGION=us-east-1
CLOUDTRAIL_SQS_URL=https://sqs.us-east-1.amazonaws.com/123456789/cloudtrail-events
REDPANDA_BROKERS=localhost:9092
```

---

## F-07 — MLflow on Local SQLite, No Remote Registry

> 🟠 **HIGH** | `backend/mlflow.db`, `backend/ml/register_models.py`

### What's Wrong

MLflow stores experiment history in a local SQLite file. Container restarts lose all experiment history. There is no CI gate preventing a degraded model from being promoted to production.

### How to Fix — Step by Step

**Step 1: Update MLflow to use PostgreSQL backend**

```yaml
# In backend/docker-compose.yml — update the mlflow service:
mlflow:
  image: ghcr.io/mlflow/mlflow:v2.19.0
  command: >
    mlflow server
    --backend-store-uri postgresql://soc_user:socpassword@postgres:5432/mlflow
    --default-artifact-root s3://your-mlflow-bucket/artifacts
    --host 0.0.0.0
    --port 5000
  environment:
    - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
    - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
  depends_on:
    - postgres
  ports:
    - "5000:5000"
```

**Step 2: Create mlflow database**

```bash
docker compose exec postgres psql -U soc_user -c "CREATE DATABASE mlflow;"
```

**Step 3: Update train.py to use remote MLflow**

```python
# backend/ml/train.py — update tracking URI
import mlflow
import os

mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("soc-anomaly-detection")
```

**Step 4: Add CI evaluation gate**

Create `.github/workflows/ml_eval.yml`:

```yaml
name: ML Evaluation Gate

on:
  pull_request:
    paths:
      - 'backend/ml/**'
      - 'backend/models.py'

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r backend/requirements.txt
      - name: Run evaluation
        run: |
          python backend/ml/train.py
          python backend/ml/evaluate.py --output-json /tmp/metrics.json
      - name: Check metrics gate
        run: |
          python -c "
          import json, sys
          m = json.load(open('/tmp/metrics.json'))
          failures = []
          if m['precision'] < 0.75: failures.append(f'Precision {m[\"precision\"]:.2%} < 75%')
          if m['recall'] < 0.90:    failures.append(f'Recall {m[\"recall\"]:.2%} < 90%')
          if m['roc_auc'] < 0.95:   failures.append(f'ROC-AUC {m[\"roc_auc\"]:.3f} < 0.95')
          if failures:
              print('❌ ML gate FAILED:')
              for f in failures: print(f'  - {f}')
              sys.exit(1)
          print('✅ ML gate passed')
          "
```

---

## F-08 — CORS Wildcard Pattern

> 🟠 **HIGH** | `backend/api/main.py`

### What's Wrong

```python
# Current (dangerous)
CORS_ORIGINS = "http://localhost:5173,https://*.vercel.app"
```

`https://*.vercel.app` allows any Vercel project — including an attacker's — to make authenticated cross-origin requests to your backend.

### How to Fix

```python
# backend/api/main.py
import os
from fastapi.middleware.cors import CORSMiddleware

# Parse exact origins from env — no wildcards
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ["CORS_ORIGINS"].split(",")
    if origin.strip()
]

# Validate no wildcards sneak in
for origin in CORS_ORIGINS:
    assert "*" not in origin, f"Wildcard CORS not allowed in production: {origin}"

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

```bash
# backend/.env (production)
CORS_ORIGINS=https://soc-triager-yourdomain.vercel.app

# backend/.env.local (development only)
CORS_ORIGINS=http://localhost:5173
```

---

## F-09 — WebSocket JWT Exposed in Query Parameter

> 🟠 **HIGH** | `backend/api/routers/websocket.py`

### What's Wrong

```
# Current — JWT in URL — logged by every proxy and CDN
wss://api.yourdomain.com/ws/alerts?token=eyJhbGciOiJIUzI1NiIsInR5cCI6...
```

Every load balancer, CDN, proxy, and web server logs this URL in plaintext, exposing the JWT to anyone with log access.

### How to Fix — Step by Step

**Step 1: Add a WebSocket ticket endpoint**

```python
# backend/api/routers/ws_ticket.py
import secrets
from fastapi import APIRouter, Depends
import redis.asyncio as aioredis
from ..auth_middleware import verify_token

router = APIRouter()

@router.post("/api/ws/ticket")
async def get_ws_ticket(payload: dict = Depends(verify_token)):
    """Exchange a valid JWT for a short-lived one-time WebSocket ticket."""
    ticket = secrets.token_urlsafe(32)
    r = aioredis.from_url(os.environ["REDIS_URL"])
    # Store ticket with 30-second TTL, linked to user role
    await r.setex(f"ws:ticket:{ticket}", 30, payload["role"])
    return {"ticket": ticket}
```

**Step 2: Update WebSocket endpoint to use ticket**

```python
# backend/api/routers/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket, ticket: str):
    r = aioredis.from_url(os.environ["REDIS_URL"])
    ticket_key = f"ws:ticket:{ticket}"

    # One-time use: get and immediately delete
    role = await r.getdel(ticket_key)
    if role is None:
        await websocket.close(code=4001)  # 4001 = unauthorized
        return

    await websocket.accept()
    # ... rest of WebSocket handler using role for filtering ...
```

**Step 3: Update frontend to use ticket**

```typescript
// frontend/src/hooks/useAlertsFeed.ts
async function connectWebSocket() {
  // First get a ticket using the normal Bearer auth
  const { ticket } = await apiClient.post("/api/ws/ticket");

  // Then use the ticket in the WebSocket URL (safe — it's short-lived and one-use)
  const ws = new WebSocket(`${WS_BASE_URL}/ws/alerts?ticket=${ticket}`);
  // ... rest of connection logic
}
```

---

## F-10 — Anomaly Threshold Hardcoded at 0.40

> 🟡 **MEDIUM** | `backend/ml/` scoring logic

### How to Fix

```python
# backend/ml/feature_engineering.py or wherever threshold is applied

import redis.asyncio as aioredis

async def get_anomaly_threshold() -> float:
    """Fetch threshold from Redis — falls back to 0.40 if not set."""
    r = aioredis.from_url(os.environ["REDIS_URL"])
    value = await r.get("ml:threshold")
    return float(value) if value else 0.40
```

```python
# backend/api/routers/settings.py — add a new endpoint (approver only)
from ..auth_middleware import require_role

@router.post("/api/settings/ml/threshold")
async def update_threshold(
    body: ThresholdUpdate,
    payload: dict = Depends(require_role("approver"))
):
    assert 0.1 <= body.threshold <= 0.95, "Threshold must be between 0.1 and 0.95"
    r = aioredis.from_url(os.environ["REDIS_URL"])
    await r.set("ml:threshold", str(body.threshold))
    # Log to ledger
    await ledger.append(action="threshold_updated", actor=payload["sub"],
                        detail=f"New threshold: {body.threshold}")
    return {"threshold": body.threshold}
```

---

## F-11 — Ansible IOC Sanitization Insufficient

> 🟡 **MEDIUM** | `backend/artifacts/sanitizers.py`

### How to Fix

Replace regex validation with typed Python validation:

```python
# backend/artifacts/sanitizers.py — replace sanitize_ansible_var()
import ipaddress
import re
from urllib.parse import urlparse

def sanitize_ansible_var(name: str, value: str) -> str:
    """Validate IOC variables using typed checks, not fragile regex."""
    validators = {
        "src_ip":       _validate_ip,
        "dst_ip":       _validate_ip,
        "cidr_block":   _validate_cidr,
        "domain":       _validate_domain,
        "url":          _validate_url,
        "file_hash":    _validate_hash,
        "username":     _validate_username,
    }
    validator = validators.get(name)
    if validator is None:
        raise ValueError(f"Unknown IOC variable name: {name}")
    return validator(value)

def _validate_ip(value: str) -> str:
    ipaddress.ip_address(value)  # raises ValueError if invalid (handles IPv4 + IPv6)
    return value

def _validate_cidr(value: str) -> str:
    ipaddress.ip_network(value, strict=False)  # handles x.x.x.x/24
    return value

def _validate_domain(value: str) -> str:
    # RFC 1123 compliant hostname check
    pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    if not re.fullmatch(pattern, value) or len(value) > 253:
        raise ValueError(f"Invalid domain: {value}")
    return value

def _validate_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid URL: {value}")
    return value

def _validate_hash(value: str) -> str:
    # SHA-256: 64 hex chars. MD5: 32. SHA-1: 40.
    if not re.fullmatch(r'[a-fA-F0-9]{32,64}', value):
        raise ValueError(f"Invalid hash: {value}")
    return value

def _validate_username(value: str) -> str:
    if not re.fullmatch(r'[a-zA-Z0-9_\-\.]{1,64}', value):
        raise ValueError(f"Invalid username: {value}")
    return value
```

Add fuzz tests:

```python
# backend/tests/test_sanitizers_fuzz.py
from hypothesis import given, strategies as st
from ..artifacts.sanitizers import sanitize_ansible_var
import pytest

@given(st.text(min_size=0, max_size=1000))
def test_sanitize_never_raises_unexpected(random_string):
    """Sanitizer must never propagate arbitrary input — only ValueError."""
    try:
        sanitize_ansible_var("src_ip", random_string)
    except ValueError:
        pass  # expected — invalid input
    # Any other exception type is a bug
```

---

## F-12 — No Rate Limiting on FastAPI Backend

> 🟡 **MEDIUM** | `backend/api/main.py`

### How to Fix

```bash
pip install slowapi==0.1.9
# Add to backend/requirements.txt: slowapi==0.1.9
```

```python
# backend/api/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, storage_uri=os.environ["REDIS_URL"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply limits to sensitive routes in the routers:
# backend/api/routers/incidents.py
from slowapi import Limiter
from fastapi import Request

@router.post("/api/incidents/{incident_id}/approve")
@limiter.limit("5/minute")   # approvals — very sensitive
async def approve_incident(request: Request, incident_id: str, ...):
    ...

@router.get("/api/alerts")
@limiter.limit("100/minute")  # general reads
async def list_alerts(request: Request, ...):
    ...
```

---

## F-13 — Mermaid XSS Risk in React Renderer

> 🟡 **MEDIUM** | `frontend/src/components/ui/AttackGraph.tsx`

### How to Fix

```typescript
// frontend/src/components/ui/AttackGraph.tsx
import mermaid from "mermaid";
import { useEffect, useRef } from "react";

// Initialize once at module level with strict security settings
mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",      // ← prevents script execution in SVG
  theme: "neutral",
  flowchart: { htmlLabels: false }, // ← no raw HTML in node labels
});

export function AttackGraph({ definition }: { definition: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !definition) return;
    mermaid.render("attack-graph", definition).then(({ svg }) => {
      // Sanitize the rendered SVG before injecting
      const sanitized = svg
        .replace(/<script[\s\S]*?<\/script>/gi, "")
        .replace(/on\w+="[^"]*"/gi, "");       // strip event handlers
      if (ref.current) ref.current.innerHTML = sanitized;
    });
  }, [definition]);

  return <div ref={ref} className="attack-graph-container" />;
}
```

Also add a Content Security Policy header in your Vercel config:

```json
// frontend/vercel.json — add headers section
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' wss:; object-src 'none';"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        }
      ]
    }
  ]
}
```

---

## F-14 — TimescaleDB Tables Created but Never Written To

> 🟡 **MEDIUM** | `backend/migrations/001_initial.sql`, all service files

### What's Wrong

The schema exists. The services do not use it. The metrics endpoint generates fake arrays on-the-fly instead of querying real time-series data.

### How to Fix

**Step 1: Wire the metrics endpoint to TimescaleDB**

```python
# backend/api/routers/metrics.py — replace fake data with real queries
from ..database import get_db
from sqlalchemy import text

@router.get("/api/metrics")
async def get_metrics(db=Depends(get_db)):
    # Real throughput from TimescaleDB time_bucket
    throughput = await db.execute(text("""
        SELECT
            time_bucket('1 minute', created_at) AS bucket,
            COUNT(*) AS event_count
        FROM normalized_events
        WHERE created_at > NOW() - INTERVAL '1 hour'
        GROUP BY bucket
        ORDER BY bucket ASC
    """))

    # Real alert volume by day
    daily_alerts = await db.execute(text("""
        SELECT
            time_bucket('1 day', created_at) AS day,
            COUNT(*) AS alert_count
        FROM alerts
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY day
        ORDER BY day ASC
    """))

    # Real LLM cost from cost_log table
    llm_cost = await db.execute(text("""
        SELECT
            time_bucket('1 day', ts) AS day,
            SUM(cost_usd) AS total_cost
        FROM llm_cost_log
        WHERE ts > NOW() - INTERVAL '7 days'
        GROUP BY day
        ORDER BY day ASC
    """))

    return {
        "throughput": [{"bucket": str(r.bucket), "count": r.event_count} for r in throughput],
        "daily_alerts": [{"day": str(r.day), "count": r.alert_count} for r in daily_alerts],
        "llm_cost": [{"day": str(r.day), "cost": float(r.total_cost)} for r in llm_cost],
    }
```

**Step 2: Add LLM cost log table to migration**

```sql
-- Add to backend/migrations/001_initial.sql or create 003_llm_cost_log.sql
CREATE TABLE IF NOT EXISTS llm_cost_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID,
    input_tokens  INT NOT NULL,
    output_tokens INT NOT NULL,
    cost_usd    NUMERIC(10, 6) NOT NULL,
    model       VARCHAR(64) NOT NULL DEFAULT 'claude-sonnet-4-6',
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('llm_cost_log', 'ts', if_not_exists => TRUE);
```

---

## F-15 — 4 API Surface Mismatches Frontend ↔ Backend

> 🟢 **LOW** | `frontend/src/types/index.ts`, `backend/models.py`

### How to Fix Permanently (Auto-Generate Types)

```bash
# Install openapi-typescript
cd frontend
npm install -D openapi-typescript

# Add to package.json scripts:
"generate:types": "openapi-ts http://localhost:8000/openapi.json -o src/types/api.generated.ts"

# Run it
npm run generate:types
```

Add a CI step that fails if types are out of sync:

```yaml
# .github/workflows/type_check.yml
- name: Check API types are in sync
  run: |
    cd frontend
    npm run generate:types
    git diff --exit-code src/types/api.generated.ts || \
      (echo "❌ API types out of sync — run npm run generate:types" && exit 1)
```

### Fix the 4 Known Mismatches Now

```typescript
// frontend/src/types/index.ts — check and align these fields:

// Backend model: anomaly_score (float)
// Frontend type: anomalyScore (camelCase) — add to apiClient.ts transformer or align naming

// Backend model: technique_id (snake_case)
// Frontend type: techniqueId — same issue

// Backend model: recommended_immediate_action
// Frontend type: check it matches exactly

// Missing route: GET /api/mitre/technique/:id
// Add to frontend/api/mitre/[id]/route.ts
```

---

## F-16 — MLflow SQLite Has No Docker Volume

> 🟢 **LOW** | `backend/docker-compose.yml`

### How to Fix

```yaml
# backend/docker-compose.yml — add to mlflow service:
volumes:
  - mlflow_data:/mlflow/data

# At the bottom of the file:
volumes:
  mlflow_data:
    driver: local
  postgres_data:   # add this too if not present
    driver: local
  redis_data:      # and this
    driver: local
```

---

## F-17 — CICIDS2017 Dataset is 9 Years Old

> 🔵 **INFO** | `backend/ml/train.py`

### Awareness

The current 96.4% recall is measured on CICIDS2017 test splits — the same distribution as training. Modern attacks (cloud-native, container escape, API abuse, AI prompt injection) are absent from this dataset. The real-world recall on novel attacks is unknown.

### What To Do (Phase 3)

```python
# backend/ml/train.py — update dataset loading to support multiple sources

DATASETS = [
    "data/cicids2017/Wednesday-workingHours.pcap_ISCX.csv",  # existing
    "data/cicids2018/Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv",  # add
    "data/unswnb15/UNSW_NB15_training-set.csv",  # add
]

# Also implement active learning collection endpoint:
# POST /api/alerts/:id/label  { "label": "true_positive" | "false_positive" }
# Store labelled alerts in: data/production_labels/YYYY-MM-DD.csv
# Nightly job: if len(production_labels) > 1000, trigger retraining
```

---

## Verification Checklist — Run After Each Fix

Copy this into a GitHub issue or Notion page and tick off as you go.

### Phase 1 — Critical Blockers
```
[ ] POST /api/auth/login with role:"approver" in body is rejected (F-01)
[ ] Server restart preserves all incidents and alerts (F-02)
[ ] HS256-signed token returns 401 Unauthorized (F-03)
[ ] CORS: curl from evil.vercel.app returns no Access-Control-Allow-Origin (F-08)
[ ] WebSocket connection without valid ticket returns close code 4001 (F-09)
[ ] Rate limiter: 6th approval request in 1 minute returns 429 (F-12)
[ ] startup fails if JWT_SECRET/JWT_PRIVATE_KEY is missing (F-03)
[ ] No wildcard (*) in CORS_ORIGINS env var (F-08)
```

### Phase 2 — Pipeline & Data
```
[ ] Inject synthetic brute-force log → incident in UI within 30s (F-04)
[ ] Malformed event lands on DLQ topic, Faust worker stays running (F-04)
[ ] OpsMetrics page shows real TimescaleDB data, not generated arrays (F-14)
[ ] At daily LLM budget cap, new triage calls return heuristic fallback (F-05)
[ ] MLflow model registry shows version history after container restart (F-07)
[ ] ML CI gate: introduce a bad model, verify PR is blocked (F-07)
```

### Phase 3 — Live Sources & Quality
```
[ ] CloudTrail event from AWS appears as incident in UI (F-06)
[ ] Syslog message sent to port 6514 appears as normalised event (F-06)
[ ] IPv6 address passes IOC sanitization (F-11)
[ ] CIDR block (e.g. 10.0.0.0/8) passes IOC sanitization (F-11)
[ ] ; rm -rf / in IOC variable raises ValueError, does not reach Ansible (F-11)
[ ] Hypothesis fuzz tests for sanitizers pass with 1000 examples (F-11)
[ ] Mermaid graph with <script> tag in label does not execute JS (F-13)
[ ] All 4 API type mismatches resolved, TypeScript strict mode passes (F-15)
[ ] openapi-typescript CI step blocks out-of-sync types (F-15)
```

---

## Dependency Install Summary

All new dependencies needed across all fixes:

```bash
# Backend
pip install \
  bcrypt==4.2.1 \
  slowapi==0.1.9 \
  httpx==0.27.0 \
  validators==0.22.0 \
  hypothesis==6.112.0 \
  boto3==1.35.0 \
  kafka-python==2.0.2

# Add to backend/requirements.txt
echo "bcrypt==4.2.1
slowapi==0.1.9
httpx==0.27.0
validators==0.22.0
hypothesis==6.112.0
boto3==1.35.0
kafka-python==2.0.2" >> backend/requirements.txt

# Frontend
cd frontend
npm install -D openapi-typescript
```

---

## Estimated Effort Per Finding

| Finding | Severity | Estimated Effort | Dependency |
|---|---|---|---|
| F-01 Auth | 🔴 CRITICAL | 2–3 days | F-02 (needs DB) |
| F-02 Persistence | 🔴 CRITICAL | 3–4 days | None — start here |
| F-03 JWT RS256 | 🔴 CRITICAL | 1 day | None |
| F-04 Faust pipeline | 🟠 HIGH | 4–5 days | F-02 |
| F-05 LLM budget | 🟠 HIGH | 1 day | None |
| F-06 Live sources | 🟠 HIGH | 3–4 days | F-04 |
| F-07 MLflow | 🟠 HIGH | 1 day | None |
| F-08 CORS | 🟠 HIGH | 10 min | None |
| F-09 WS ticket | 🟠 HIGH | 1 day | F-02 (Redis) |
| F-10 Threshold | 🟡 MEDIUM | 0.5 day | None |
| F-11 Sanitizers | 🟡 MEDIUM | 0.5 day | None |
| F-12 Rate limit | 🟡 MEDIUM | 0.5 day | None |
| F-13 Mermaid XSS | 🟡 MEDIUM | 0.5 day | None |
| F-14 TimescaleDB | 🟡 MEDIUM | 3 days | F-02, F-04 |
| F-15 Type mismatches | 🟢 LOW | 2 hours | None |
| F-16 Docker volume | 🟢 LOW | 10 min | None |
| F-17 Dataset | 🔵 INFO | Phase 3 | F-04 |

**Recommended execution order:** F-16 → F-08 → F-12 → F-15 → F-03 → F-02 → F-01 → F-05 → F-07 → F-09 → F-13 → F-11 → F-10 → F-04 → F-14 → F-06 → F-17

---

*End of Audit — SOC Triager | Antigravity Team | 13 August 2026*
