"""
Tests for scorer.py
"""
import pytest
import numpy as np
import torch
from unittest.mock import patch, MagicMock
from backend.ml import scorer

@pytest.fixture
def mock_models():
    # Mock isolation forest
    mock_if = MagicMock()
    mock_if.score_samples.return_value = np.array([-0.6]) # will produce ~0.06
    
    # Mock autoencoder
    mock_ae = MagicMock()
    # Returns the input to give 0 MSE
    mock_ae.side_effect = lambda x: x
    
    with patch("backend.ml.scorer._if_model", mock_if), patch("backend.ml.scorer._ae_model", mock_ae):
        yield mock_if, mock_ae

def test_score_events(mock_models):
    events = [{"source": {"ip": "192.168.1.1"}}]
    
    # Score events, skipping model loading by mocking _load_models
    with patch("backend.ml.scorer._load_models"):
        results = scorer.score_events(events)
        
    assert len(results) == 1
    scored = results[0]
    assert "anomaly_score" in scored
    assert "top_features" in scored
    assert len(scored["top_features"]) == 3
