import pickle
import numpy as np
import torch
from pathlib import Path
from typing import List, Dict, Any

from .feature_engineering import extract_features
from .autoencoder import Autoencoder
from ..config import MODEL_DIR, IF_WEIGHT, AE_WEIGHT, AE_BENIGN_P95

_if_model = None
_ae_model = None


def _load_models():
    global _if_model, _ae_model
    model_dir = Path(MODEL_DIR)
    if _if_model is None:
        with open(model_dir / "isolation_forest.pkl", "rb") as f:
            _if_model = pickle.load(f)
    if _ae_model is None:
        ae = Autoencoder(input_dim=9)
        ae.load_state_dict(torch.load(str(model_dir / "autoencoder.pt"), map_location="cpu", weights_only=True))
        ae.eval()
        _ae_model = ae


def score_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            mse = float(torch.nn.functional.mse_loss(recon, tensor).item())
        ae_score = float(np.clip(mse / AE_BENIGN_P95, 0, 1))

        ensemble = IF_WEIGHT * if_score + AE_WEIGHT * ae_score

        feature_names = [
            "event_count_1m", "event_count_5m", "event_count_1h",
            "failed_auth_ratio", "distinct_dest_ports", "dest_ip_fanout",
            "bytes_transferred", "tod_zscore", "geo_velocity_kmh",
        ]
        contributions = list(zip(feature_names, np.abs(features - 0.5)))
        top3 = sorted(contributions, key=lambda x: x[1], reverse=True)[:3]

        result = dict(event)
        result["anomaly_score"] = round(ensemble, 4)
        result["top_features"] = [{"name": n, "value": round(float(v), 4)} for n, v in top3]
        results.append(result)

    return results

