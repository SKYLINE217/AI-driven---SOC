import joblib
import numpy as np
import torch
from pathlib import Path
from typing import List, Dict, Any

from .feature_engineering import extract_features, reset_state
from .autoencoder import Autoencoder
from ..config import MODEL_DIR, IF_WEIGHT, AE_WEIGHT, AE_BENIGN_P95

_if_model = None
_ae_model = None

FEATURE_NAMES = [
    "event_count_1m", "event_count_5m", "event_count_1h",
    "failed_auth_ratio", "distinct_dest_ports", "dest_ip_fanout",
    "bytes_transferred", "tod_zscore", "geo_velocity_kmh",
]


def _load_models():
    global _if_model, _ae_model
    model_dir = Path(MODEL_DIR)
    if_path = model_dir / "isolation_forest.pkl"
    ae_path = model_dir / "autoencoder.pt"

    if not if_path.exists() or not ae_path.exists():
        raise FileNotFoundError(f"Model files not found in {model_dir}")

    if _if_model is None:
        _if_model = joblib.load(if_path)
    if _ae_model is None:
        ae = Autoencoder(input_dim=9)
        ae.load_state_dict(torch.load(str(ae_path), map_location="cpu", weights_only=True))
        ae.eval()
        _ae_model = ae


def score_events(events: List[Dict[str, Any]], reset: bool = False) -> List[Dict[str, Any]]:
    """
    Score a sequence of normalized log events with the IF + Autoencoder ensemble.
    Computes principled per-feature anomaly attribution based on reconstruction error and feature magnitude.
    """
    if reset:
        reset_state()

    _load_models()
    results = []
    for event in events:
        features = extract_features(event)
        vec = features.reshape(1, -1)

        raw_if = -_if_model.score_samples(vec)[0]
        if_score = float(np.clip((raw_if + 0.5) / 1.5, 0, 1))

        with torch.no_grad():
            tensor = torch.FloatTensor(vec)
            recon = _ae_model(tensor)
            recon_np = recon.numpy().flatten()
            per_feat_recon_err = (recon_np - features) ** 2
            mse = float(per_feat_recon_err.mean())
        ae_score = float(np.clip(mse / AE_BENIGN_P95, 0, 1))

        ensemble = IF_WEIGHT * if_score + AE_WEIGHT * ae_score

        # Meaningful model-derived feature attribution:
        # Combine Autoencoder reconstruction error with raw feature impact
        feat_importance = per_feat_recon_err + 0.1 * np.abs(features)
        contributions = list(zip(FEATURE_NAMES, feat_importance, features))
        top3 = sorted(contributions, key=lambda x: x[1], reverse=True)[:3]

        result = dict(event)
        result["anomaly_score"] = round(ensemble, 4)
        result["top_features"] = [{"name": n, "value": round(float(raw_val), 4)} for n, imp, raw_val in top3]
        results.append(result)

    return results

