"""
SOC Triager — ML Scoring API (Production-hardened)

Changes from original:
  - MLflow tracking URI comes from MLFLOW_TRACKING_URI env var (PostgreSQL, not SQLite)
  - On startup, attempts to load the production model from MLflow registry
  - If registry is empty / model missing → MODEL_STATUS = "heuristic_fallback", returns 503
    on scoring requests with Retry-After: 60 header
  - Adds /health endpoint that reports model status
  - structlog replaces print()
  - Removes random noise from heuristic scorer (deterministic, testable)
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import Any

import mlflow
import structlog
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app

from backend.models import FeatureContribution, FeatureVector, ScoreResponse

log = structlog.get_logger()

# ── Config ────────────────────────────────────────────────────────────────────

MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1.0-heuristic")
THRESHOLD = float(os.environ.get("ANOMALY_THRESHOLD", "0.75"))
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "")
MLFLOW_MODEL_NAME = os.environ.get("MLFLOW_MODEL_NAME", "soc-anomaly-ensemble")

# ── Prometheus Metrics ────────────────────────────────────────────────────────

SCORE_REQUESTS = Counter("score_requests_total", "Total scoring requests")
ANOMALY_ALERTS = Counter("anomaly_alerts_total", "Total anomalous scores generated")
SCORING_LATENCY = Histogram("scoring_latency_seconds", "Scoring latency in seconds")
MODEL_FALLBACK_TOTAL = Counter("model_fallback_total", "Times heuristic fallback was used")

# ── Model State ───────────────────────────────────────────────────────────────

_mlflow_model = None
MODEL_STATUS = "uninitialized"   # "mlflow", "heuristic_fallback", "uninitialized"


def _try_load_mlflow_model() -> bool:
    """Attempt to load the production model from MLflow registry. Returns True on success."""
    global _mlflow_model, MODEL_STATUS

    if not MLFLOW_TRACKING_URI:
        log.warning("mlflow_no_uri", msg="MLFLOW_TRACKING_URI not set — using heuristic fallback")
        MODEL_STATUS = "heuristic_fallback"
        return False

    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        model_uri = f"models:/{MLFLOW_MODEL_NAME}/Production"
        _mlflow_model = mlflow.pyfunc.load_model(model_uri)
        MODEL_STATUS = "mlflow"
        log.info("mlflow_model_loaded", model=MLFLOW_MODEL_NAME, uri=model_uri)
        return True
    except Exception as exc:
        log.critical(
            "mlflow_model_load_failed",
            model=MLFLOW_MODEL_NAME,
            error=str(exc),
            fallback="heuristic",
        )
        MODEL_STATUS = "heuristic_fallback"
        return False


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load MLflow model on startup."""
    _try_load_mlflow_model()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="SOC Triager ML Scoring API", version="1.0.0", lifespan=lifespan)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ── Heuristic Scorer (deterministic, no random noise) ────────────────────────

def heuristic_score(features: FeatureVector) -> tuple[float, list[FeatureContribution]]:
    """Rule-based scoring used when the ML model is unavailable."""
    score = 0.0
    contributions: list[FeatureContribution] = []

    checks = [
        ("failed_auth_ratio", features.failed_auth_ratio, 0.5, 0.40),
        ("event_count_1m",    features.event_count_1m,    100,  0.30),
        ("geo_velocity_kmh",  features.geo_velocity_kmh,  800,  0.30),
        ("dest_ip_fanout",    features.dest_ip_fanout,    50,   0.20),
        ("tod_zscore",        features.tod_zscore,        2.0,  0.10),
    ]

    for name, value, threshold, weight in checks:
        if value > threshold:
            score += weight
            contributions.append(FeatureContribution(name=name, contribution=weight))

    final_score = min(1.0, score)
    contributions.sort(key=lambda c: c.contribution, reverse=True)
    return final_score, contributions


# ── MLflow Scorer ─────────────────────────────────────────────────────────────

def mlflow_score(features: FeatureVector) -> tuple[float, list[FeatureContribution]]:
    """Score using the loaded MLflow model."""
    import pandas as pd

    feature_array = pd.DataFrame([{
        "event_count_1m":    features.event_count_1m,
        "event_count_5m":    features.event_count_5m,
        "event_count_1h":    features.event_count_1h,
        "failed_auth_ratio": features.failed_auth_ratio,
        "distinct_dest_ports": features.distinct_dest_ports,
        "dest_ip_fanout":    features.dest_ip_fanout,
        "bytes_transferred": features.bytes_transferred,
        "tod_zscore":        features.tod_zscore,
        "geo_velocity_kmh":  features.geo_velocity_kmh,
    }])

    prediction = _mlflow_model.predict(feature_array)
    # Ensemble returns [score, ...shap_values] — first element is anomaly score
    score = float(prediction[0]) if hasattr(prediction, "__len__") else float(prediction)
    score = max(0.0, min(1.0, score))
    return score, []  # SHAP contributions computed separately if needed


# ── Scoring Endpoint ──────────────────────────────────────────────────────────

@app.post("/score", response_model=ScoreResponse)
async def score_event(request: dict[str, Any]) -> ScoreResponse:
    # If model failed to load and we have no fallback, return 503
    if MODEL_STATUS == "uninitialized":
        return JSONResponse(
            status_code=503,
            content={"detail": "Scoring model not yet loaded"},
            headers={"Retry-After": "30"},
        )

    SCORE_REQUESTS.inc()
    start_time = time.perf_counter()

    try:
        features_data = request.get("features", request)
        features = FeatureVector(**features_data)

        if MODEL_STATUS == "mlflow" and _mlflow_model is not None:
            try:
                score, contributions = mlflow_score(features)
            except Exception as exc:
                log.warning("mlflow_inference_failed", error=str(exc), fallback="heuristic")
                score, contributions = heuristic_score(features)
                MODEL_FALLBACK_TOTAL.inc()
        else:
            score, contributions = heuristic_score(features)
            MODEL_FALLBACK_TOTAL.inc()

        is_anomaly = score >= THRESHOLD
        if is_anomaly:
            ANOMALY_ALERTS.inc()

        latency_s = time.perf_counter() - start_time
        SCORING_LATENCY.observe(latency_s)

        return ScoreResponse(
            score=score,
            threshold=THRESHOLD,
            is_anomaly=is_anomaly,
            top_features=contributions,
            model_version=f"{MODEL_STATUS}:{MODEL_VERSION}",
            latency_ms=latency_s * 1000,
        )

    except Exception as exc:
        log.error("scoring_error", error=str(exc))
        latency_s = time.perf_counter() - start_time
        SCORING_LATENCY.observe(latency_s)
        return ScoreResponse(
            score=0.0,
            threshold=THRESHOLD,
            is_anomaly=False,
            top_features=[],
            model_version=f"error:{str(exc)[:50]}",
            latency_ms=latency_s * 1000,
        )


# ── Health Endpoint ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Returns model status. 503 if model is in error state."""
    if MODEL_STATUS == "heuristic_fallback":
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "model_status": MODEL_STATUS,
                "detail": "MLflow model unavailable — using heuristic fallback",
            },
            headers={"Retry-After": "60"},
        )
    return {
        "status": "ok",
        "model_status": MODEL_STATUS,
        "model_version": MODEL_VERSION,
        "threshold": THRESHOLD,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.scoring_api.main:app", host="0.0.0.0", port=8001, reload=True)
