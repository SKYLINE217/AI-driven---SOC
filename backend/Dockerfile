# SOC Triager — Multi-stage Production Dockerfile
# Stage 1: builder — installs all deps including dev tools
# Stage 2: runtime — copies ONLY production code, excludes test data generators

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps for asyncpg, cryptography, torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt --target /deps


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system deps only (no gcc, no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /deps /usr/local/lib/python3.12/site-packages/

# Copy ONLY production source directories
# Explicitly EXCLUDE: ingestion/generators, tests, mlartifacts, mlflow.db
COPY backend/api/          /app/backend/api/
COPY backend/db/           /app/backend/db/
COPY backend/llm/          /app/backend/llm/
COPY backend/metrics/      /app/backend/metrics/
COPY backend/middleware/   /app/backend/middleware/
COPY backend/mitre/        /app/backend/mitre/
COPY backend/ml/           /app/backend/ml/
COPY backend/stream/       /app/backend/stream/
COPY backend/scoring_api/  /app/backend/scoring_api/
COPY backend/artifacts/    /app/backend/artifacts/
COPY backend/models.py     /app/backend/models.py
COPY backend/__init__.py   /app/backend/__init__.py

# ── Non-root user ─────────────────────────────────────────────────────────────
RUN groupadd -r socapp && useradd -r -g socapp -s /bin/false socapp
USER socapp

# ── Environment defaults (override at runtime) ────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
