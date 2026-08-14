"""
Tests for model training module.
"""
import pandas as pd
import numpy as np
from backend.ml.train import extract_features

def test_extract_features():
    df = pd.DataFrame({
        ' Total Fwd Packets': [10, 0, 5],
        ' Total Backward Packets': [5, 0, 5],
        ' Destination Port': [80, 443, 22],
        ' Flow Bytes/s': [1000, 2000, 500]
    })
    
    features = extract_features(df)
    
    assert len(features) == 3
    assert 'event_count_1m' in features.columns
    assert 'failed_auth_ratio' in features.columns
    
    # Verify values are normalized (except z-score which can be negative)
    for col in features.columns:
        if col != 'tod_zscore':
            assert features[col].max() <= 1.0
            assert features[col].min() >= 0.0
