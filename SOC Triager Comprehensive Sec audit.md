# 🛡️ SOC Triager: Comprehensive Security & Architecture Audit Report

**Date:** August 14, 2026  
**Target Repository:** `SKYLINE217/AI-driven---SOC`  
**Project Name:** SOC Triager (AI-Driven Security Operations Center Automation Platform)  
**Auditor:** Principal AI Security & Architecture Engine  

---

## 1. Executive Summary

**SOC Triager** is an ambitious and highly sophisticated autonomous Tier-1/Tier-2 SOC platform. It successfully integrates Faust stream processing, Isolation Forest/Autoencoder ensembles, MITRE ATT&CK mapping, and Claude LLM triage into a React/Vite dashboard. The core machine learning pipeline achieves an impressive **96.4% recall** and **87.4% F1-score**.

However, a deep-dive audit reveals **17 distinct vulnerabilities and architectural flaws** that currently render the system unsuitable for production deployment. The most severe issues include **trivial authentication bypasses**, **volatile in-memory data stores** that destroy forensic chain-of-custody upon restart, and **unbounded LLM cost vectors** that could lead to catastrophic cloud billing events during a log-flood attack.

This report provides an exhaustive breakdown of every identified flaw, the exact risk it poses to a Security Operations Center, and the precise code-level remediation required to harden the platform.

---

## 2. Audit Methodology

The audit was conducted across four primary dimensions:
1. **Security Posture:** Authentication, Authorization (RBAC), Cryptography, Input Sanitization, and OWASP Top 10 vectors.
2. **Data Durability & Integrity:** Persistence layers, audit ledger continuity, and state management.
3. **System Architecture:** Stream processing wiring, microservice communication, and infrastructure-as-code (Docker/Helm).
4. **Operational Viability:** Cost controls, observability, rate limiting, and real-world integration readiness.

---

## 3. Critical Findings (🔴 CRITICAL)
*Issues that allow immediate unauthorized access, data destruction, or complete system compromise.*

### [F-01] Broken Authentication & Trivial Role Escalation
* **Location:** `frontend/src/pages/Login.tsx`, `backend/api/routers/auth.py`
* **Description:** The login mechanism does not validate passwords. The frontend sends a JSON payload containing a `role` field (e.g., `{"username": "admin", "role": "approver"}`). The backend blindly trusts this client-supplied role and embeds it directly into the JWT.
* **Impact:** **Complete Platform Takeover.** Any external actor who discovers the `/api/auth/login` endpoint can instantly mint an "Approver" JWT. This grants them the ability to approve Ansible containment playbooks, allowing them to shut down production infrastructure or isolate critical business units.
* **Remediation:**
  1. Implement a PostgreSQL `users` table with `bcrypt` password hashing.
  2. Remove the `role` field from the login request schema.
  3. Fetch the user's role exclusively from the database during the authentication handshake.
  ```python
  # backend/api/routers/auth.py
  class LoginRequest(BaseModel):
      username: str
      password: str # Replaced 'role'

  @router.post("/api/auth/login")
  async def login(req: LoginRequest, db=Depends(get_db)):
      user = await db.fetch_one("SELECT * FROM users WHERE username = :u", {"u": req.username})
      if not user or not bcrypt.checkpw(req.password.encode(), user.password_hash.encode()):
          raise HTTPException(status_code=401, detail="Invalid credentials")
      # Role is derived from DB, never client
      token = create_access_token({"sub": user.username, "role": user.role})
      return {"access_token": token}
  ```

### [F-02] Volatile In-Memory Incident Store (Forensic Data Loss)
* **Location:** `backend/api/incident_service.py`
* **Description:** The `IncidentService` class stores all alerts, incidents, and the SHA-256 hash-chained audit ledger in Python dictionaries (`self.incidents = {}`) within the process memory. It seeds fake data on every startup.
* **Impact:** **Loss of Forensic Evidence.** If the backend container crashes, restarts, or scales horizontally, all active investigations, historical alerts, and the cryptographic chain of custody are permanently destroyed. This violates core SOC compliance requirements (e.g., SOC2, ISO27001).
* **Remediation:**
  1. Deprecate the in-memory dictionaries.
  2. Implement SQLAlchemy Async ORM models for `DBIncident` and `DBLedgerEntry`.
  3. Persist all state to the existing PostgreSQL/TimescaleDB instance.
  4. Remove the `_seed_data()` method from the production code path.

### [F-03] Symmetric JWT Cryptography (HS256)
* **Location:** `backend/api/auth_middleware.py`
* **Description:** The system uses HS256 (HMAC-SHA256) for JWT signing. This symmetric algorithm uses the exact same secret key to both *sign* and *verify* tokens.
* **Impact:** **Lateral Movement & Forgery.** In a microservices architecture, any service that needs to verify a token (like the frontend BFF or WebSocket gateway) must possess the signing secret. If any peripheral service is compromised, the attacker can forge valid administrative tokens for the entire platform.
* **Remediation:**
  1. Generate an RSA-2048 key pair.
  2. Use the **Private Key** strictly for signing tokens in the Auth Service.
  3. Distribute the **Public Key** to all verifying services.
  4. Update `auth_middleware.py` to enforce `algorithm="RS256"`.

---

## 4. High Severity Findings (🟠 HIGH)
*Issues that cause severe operational instability, financial risk, or bypass security controls.*

### [F-04] Skeleton Faust Streaming Pipeline
* **Location:** `backend/stream/faust_app.py`
* **Description:** The Redpanda/Kafka stream processing agents are currently unwired skeletons. They do not pass data through the normalizers, feature store, or ML scoring API.
* **Impact:** The system is entirely reliant on seeded mock data. No real-time log ingestion or anomaly detection is actually occurring in the pipeline.
* **Remediation:** Wire the Faust agents to subscribe to `raw.*` topics, invoke the `get_normalizer()` registry, POST features to the `:8001/score` API, and route anomalies to the MITRE clustering engine. Implement a Dead Letter Queue (DLQ) for malformed events.

### [F-05] Unbounded LLM Cost Vector (No Circuit Breaker)
* **Location:** `backend/llm/triage_client.py`
* **Description:** Every anomaly that crosses the 0.40 threshold immediately triggers a synchronous Claude Sonnet API call. There is no daily budget cap, rate limiting, or batching logic.
* **Impact:** **Financial Denial of Service.** An attacker generating a high-volume log flood (e.g., DDoS or port scan) will trigger thousands of LLM calls per minute. At ~$0.015 per 1k output tokens, a coordinated attack could generate tens of thousands of dollars in API billing in a single hour.
* **Remediation:** Implement a Redis-backed daily spend tracker.
  ```python
  async def check_budget(input_tokens):
      daily_spend = float(await redis.get("llm:daily_spend") or 0)
      if daily_spend >= DAILY_BUDGET_USD:
          return False # Trip breaker -> fallback to heuristic-only triage
      await redis.incrbyfloat("llm:daily_spend", calculate_cost(input_tokens))
      return True
  ```

### [F-06] Lack of Real Log Source Integration
* **Location:** `backend/ingestion/generators/`
* **Description:** The platform only includes Python scripts that generate synthetic mock logs. There are no live connectors for AWS CloudTrail, Syslog, or SIEM webhooks.
* **Remediation:** Build production connectors:
  1. **AWS CloudTrail:** EventBridge → SQS → Redpanda poller.
  2. **Syslog:** Asyncio TLS TCP listener on port 6514.

### [F-07] MLflow Local SQLite & Lack of CI Gating
* **Location:** `backend/docker-compose.yml`, `backend/ml/`
* **Description:** MLflow tracks experiments in a local SQLite file inside the container. Furthermore, there is no CI/CD pipeline gate to prevent a degraded ML model from being promoted to production.
* **Remediation:** Point MLflow's `--backend-store-uri` to PostgreSQL and `--default-artifact-root` to S3. Implement a GitHub Actions workflow that runs `evaluate.py` and blocks PR merges if Recall < 90% or ROC-AUC < 0.95.

### [F-08] Dangerous CORS Wildcard Pattern
* **Location:** `backend/api/main.py`
* **Description:** `CORS_ORIGINS` is configured as `https://*.vercel.app`.
* **Impact:** Any malicious actor can deploy a phishing site on Vercel (e.g., `soc-login.vercel.app`) and make authenticated cross-origin requests to your backend, stealing data or executing actions via the victim's active session.
* **Remediation:** Parse exact origins from environment variables and explicitly reject wildcards (`*`) in production.

### [F-09] WebSocket JWT Exposed in Query Parameters
* **Location:** `backend/api/routers/websocket.py`
* **Description:** The frontend connects to the WebSocket via `wss://api/ws/alerts?token=<JWT>`.
* **Impact:** **Token Leakage.** URL query parameters are logged in plaintext by every CDN, reverse proxy, load balancer, and web server access log. Anyone with read access to infrastructure logs can steal active admin sessions.
* **Remediation:** Implement a **One-Time Ticket System**.
  1. Frontend calls `POST /api/ws/ticket` (using standard Bearer Auth).
  2. Backend generates a 30-second Redis key and returns the ticket.
  3. Frontend connects to WebSocket using `?ticket=XYZ`. Backend validates and instantly deletes the ticket.

---

## 5. Medium Severity Findings (🟡 MEDIUM)
*Issues that degrade security posture, introduce injection risks, or result in inaccurate reporting.*

### [F-10] Hardcoded Anomaly Threshold (0.40)
* **Description:** The ML threshold is hardcoded in the Python logic. SOC analysts cannot tune the precision/recall trade-off without a full code deployment.
* **Remediation:** Store the threshold in Redis (`ml:threshold`). Create an Approver-only API endpoint to update it dynamically.

### [F-11] Insufficient Ansible IOC Sanitization (Command Injection)
* **Location:** `backend/artifacts/sanitizers.py`
* **Description:** Indicators of Compromise (IPs, domains) are sanitized using fragile Regex before being injected into Ansible containment playbooks.
* **Impact:** **Remote Code Execution (RCE).** An attacker who crafts a malicious log entry (e.g., an IP field containing `; rm -rf /`) could bypass the regex and execute arbitrary shell commands on the server generating the playbook.
* **Remediation:** Replace Regex with strict Python standard library typing:
  ```python
  import ipaddress
  def validate_ioc(name, value):
      if name in ["src_ip", "dst_ip"]:
          ipaddress.ip_address(value) # Raises ValueError if invalid
      return value
  ```

### [F-12] Missing API Rate Limiting
* **Location:** `backend/api/main.py`
* **Description:** FastAPI endpoints have no rate limits.
* **Impact:** Vulnerable to brute-force attacks, credential stuffing, and application-layer DoS.
* **Remediation:** Implement `slowapi` with a Redis backend. Apply strict limits to state-changing routes (e.g., `5/minute` for playbook approvals).

### [F-13] Mermaid XSS Risk in React Renderer
* **Location:** `frontend/src/components/ui/AttackGraph.tsx`
* **Description:** The Mermaid.js library is rendering attack graphs without strict security configurations.
* **Impact:** If an attacker injects malicious payloads into log fields that end up in the Mermaid definition, it could trigger Cross-Site Scripting (XSS) in the SOC analyst's browser.
* **Remediation:** Initialize Mermaid with `securityLevel: 'strict'` and `flowchart: { htmlLabels: false }`. Enforce a strict Content Security Policy (CSP) via Vercel headers.

### [F-14] Disconnected TimescaleDB (Fake Metrics)
* **Location:** `backend/api/routers/metrics.py`
* **Description:** The dashboard's "Ops Metrics" tab generates random arrays using Python's `random` module instead of querying the provisioned TimescaleDB.
* **Remediation:** Replace mock data with real `time_bucket()` SQL queries against the `normalized_events` and `llm_cost_log` hypertables.

---

## 6. Low & Informational Findings (🟢 LOW / 🔵 INFO)

### [F-15] API Surface Mismatches (Frontend ↔ Backend)
* **Description:** 4 minor field name mismatches (e.g., `anomaly_score` vs `anomalyScore`) and a missing route (`GET /api/mitre/technique/:id`).
* **Remediation:** Integrate `openapi-typescript` into the CI pipeline to auto-generate frontend TypeScript interfaces directly from the FastAPI `openapi.json` schema.

### [F-16] Ephemeral MLflow Docker Volume
* **Description:** The MLflow container lacks a mapped Docker volume, meaning experiment history is lost if the container is rebuilt.
* **Remediation:** Add `mlflow_data:/mlflow` to the `volumes` section of `docker-compose.yml`.

### [F-17] Outdated Training Dataset (CICIDS2017)
* **Description:** The ML ensemble is trained exclusively on CICIDS2017, which lacks modern cloud-native, container-escape, and API-abuse attack vectors.
* **Remediation:** Incorporate CICIDS2018 and UNSW-NB15 datasets. Implement an "Active Learning" endpoint allowing analysts to flag False Positives, creating a continuous feedback loop for nightly model retraining.

---

## 7. Strategic Architecture Recommendations

To transition SOC Triager from a "Proof of Concept" to an "Enterprise-Grade SOC Platform", the following architectural shifts are required:

1. **Shift from Sync to Async Triage:** The current synchronous LLM call blocks the streaming pipeline. Move LLM triage to an asynchronous task queue (e.g., Celery or ARQ) backed by Redis, allowing the ML scoring engine to process thousands of events per second without waiting for Claude's response.
2. **Implement Zero-Trust Networking:** Currently, internal microservices (Faust, Scoring API, FastAPI) communicate over plaintext HTTP. Implement mutual TLS (mTLS) or a service mesh (like Istio/Linkerd) for internal east-west traffic.
3. **Secrets Management:** Migrate away from `.env` files. Integrate HashiCorp Vault or AWS Secrets Manager to dynamically inject DB credentials and API keys into the Kubernetes pods at runtime.

---

## 8. Remediation Roadmap

### Phase 1: Immediate Triage (Days 1-3)
*Focus: Stopping active bleeding and securing the perimeter.*
- [ ] **Fix F-01:** Implement bcrypt password validation and DB-backed roles.
- [ ] **Fix F-03:** Rotate to RS256 asymmetric JWTs.
- [ ] **Fix F-08:** Lock down CORS to exact production domains.
- [ ] **Fix F-09:** Implement WebSocket one-time ticketing.
- [ ] **Fix F-12:** Deploy `slowapi` rate limiting.

### Phase 2: Data Durability & Pipeline Wiring (Days 4-10)
*Focus: Ensuring data survives restarts and the pipeline actually processes logs.*
- [ ] **Fix F-02:** Migrate `IncidentService` to SQLAlchemy/PostgreSQL.
- [ ] **Fix F-04:** Wire Faust agents to normalizers and the ML scoring API.
- [ ] **Fix F-14:** Connect TimescaleDB to the frontend metrics dashboard.
- [ ] **Fix F-05:** Deploy the LLM cost circuit-breaker.

### Phase 3: Production Hardening & Integrations (Days 11-20)
*Focus: Real-world connectivity and defense-in-depth.*
- [ ] **Fix F-06:** Deploy live CloudTrail (SQS) and Syslog (TLS) listeners.
- [ ] **Fix F-11:** Refactor IOC sanitization to use `ipaddress` and `urlparse`.
- [ ] **Fix F-13:** Enforce strict Mermaid rendering and CSP headers.
- [ ] **Fix F-07:** Migrate MLflow to PostgreSQL/S3 and implement CI gates.

---

## 9. Conclusion

The **SOC Triager** repository demonstrates exceptional promise. The mathematical rigor applied to the Isolation Forest/Autoencoder ensemble and the creative use of LLMs for MITRE ATT&CK mapping represent cutting-edge SOC automation. 

However, the current implementation operates under the assumption of a trusted, isolated environment. By executing the remediation steps outlined in this report—specifically addressing the **Authentication Bypass (F-01)**, **Data Volatility (F-02)**, and **LLM Cost Vectors (F-05)**—the engineering team will transform this project from a highly capable academic prototype into a resilient, enterprise-ready security product.

***

*End of Report. Save this document as `AUDIT_REPORT.md` in the root of your repository for tracking and compliance purposes.*