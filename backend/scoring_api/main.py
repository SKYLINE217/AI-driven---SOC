import os
import random
import time
from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Histogram
from backend.models import FeatureVector, ScoreResponse, FeatureContribution

app = FastAPI(title="SOC Triager ML Scoring API")

# Prometheus Metrics
SCORE_REQUESTS = Counter("score_requests_total", "Total scoring requests")
ANOMALY_ALERTS = Counter("anomaly_alerts_total", "Total anomalous scores generated")
SCORING_LATENCY = Histogram("scoring_latency_seconds", "Latency of ML scoring")

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1.0-heuristic")
THRESHOLD = float(os.environ.get("ANOMALY_THRESHOLD", "0.75"))

def heuristic_score(features: FeatureVector) -> tuple[float, list[FeatureContribution]]:
    """
    Mock ML model using heuristics for demonstration.
    In a real scenario, this would load a scikit-learn or PyTorch model via MLflow.
    """
    score = 0.0
    contributions = []
    
    # Simple rule-based mock
    if features.failed_auth_ratio > 0.5:
        score += 0.4
        contributions.append(FeatureContribution(name="failed_auth_ratio", contribution=0.4))
        
    if features.event_count_1m > 100:
        score += 0.3
        contributions.append(FeatureContribution(name="event_count_1m", contribution=0.3))
        
    if features.geo_velocity_kmh > 800:
        score += 0.3
        contributions.append(FeatureContribution(name="geo_velocity_kmh", contribution=0.3))
        
    if features.dest_ip_fanout > 50:
        score += 0.2
        contributions.append(FeatureContribution(name="dest_ip_fanout", contribution=0.2))
        
    if features.tod_zscore > 2.0:
        score += 0.1
        contributions.append(FeatureContribution(name="tod_zscore", contribution=0.1))
        
    # Baseline noise
    noise = random.uniform(0.0, 0.1)
    score += noise
    
    # Cap at 1.0
    final_score = min(1.0, score)
    
    if len(contributions) == 0 and noise > 0:
        contributions.append(FeatureContribution(name="baseline_noise", contribution=noise))
        
    # Sort contributions by impact
    contributions.sort(key=lambda x: x.contribution, reverse=True)
    
    return final_score, contributions


@app.post("/score", response_model=ScoreResponse)
async def score_event(request: dict) -> ScoreResponse:
    SCORE_REQUESTS.inc()
    start_time = time.perf_counter()
    
    try:
        # Extract features from request
        # The Faust worker might pass just the raw JSON for the features
        if "features" in request:
            features = FeatureVector(**request["features"])
        else:
            features = FeatureVector(**request)
            
        score, contributions = heuristic_score(features)
        
        is_anomaly = score >= THRESHOLD
        if is_anomaly:
            ANOMALY_ALERTS.inc()
            
        latency_ms = (time.perf_counter() - start_time) * 1000
        SCORING_LATENCY.observe(latency_ms / 1000.0)
        
        return ScoreResponse(
            score=score,
            threshold=THRESHOLD,
            is_anomaly=is_anomaly,
            top_features=contributions,
            model_version=MODEL_VERSION,
            latency_ms=latency_ms
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        # Return a safe non-anomalous response on error for now
        return ScoreResponse(
            score=0.0,
            threshold=THRESHOLD,
            is_anomaly=False,
            top_features=[],
            model_version=f"error: {str(e)}",
            latency_ms=latency_ms
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.scoring_api.main:app", host="0.0.0.0", port=8001, reload=True)
