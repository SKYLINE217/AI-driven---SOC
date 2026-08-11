# SOC Triager — AI-driven Security Operations Center

SOC Triager is a high-performance, real-time alert triage and containment platform. It ingests massive volumes of normalized security logs via Redpanda (Kafka), computes anomaly scores using machine learning, clusters related events, and uses an LLM to generate actionable containment playbooks.

## Architecture

![System Architecture](../docs/architecture.png)
*(Note: A high-level system architecture diagram belongs here.)*

- **Frontend (Vercel):** React 18, Vite, Zustand, Tailwind/Custom CSS.
- **BFF (Vercel Serverless/Edge):** JWT validation, rate limiting, role-based access control (RBAC), backend API proxying.
- **Backend (FastAPI):** Python microservices for Incident Correlation, ML Scoring, and WebSocket broadcasting.
- **Data & Streaming:** Redpanda (Kafka) for event bus, TimescaleDB (Postgres) for incidents and feature store, Redis for Pub/Sub.

## Local Setup

### 1. Backend Infrastructure (Docker)
Ensure Docker is installed and running, then spin up the backend dependencies:
```bash
cd backend
docker compose up -d
```
*This starts Redpanda, Redis, TimescaleDB, MLflow, Prometheus, and Grafana.*

### 2. Frontend (Vite)
Run the frontend locally in development mode:
```bash
cd frontend
npm install
npm run dev
```
Alternatively, to simulate the Edge Middleware and serverless BFF locally, use Vercel CLI:
```bash
vercel dev
```

## Security & RBAC
The system utilizes a strict Role-Based Access Control (RBAC) model managed via JWTs:
- **Analyst:** Can view and acknowledge alerts, view playbooks.
- **Senior Analyst:** Can escalate and close incidents.
- **Approver:** Can execute (approve) automated containment playbooks.
