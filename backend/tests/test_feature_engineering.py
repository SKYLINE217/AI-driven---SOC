import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC

from backend.ml.feature_engineering import compute_windowed_features
from backend.models import FeatureVector


@pytest.mark.asyncio
async def test_compute_windowed_features_empty():
    """Test feature extraction when Redis has no history for the entity."""
    mock_redis = MagicMock()
    mock_pipeline = AsyncMock()
    mock_redis.pipeline.return_value = mock_pipeline
    
    # Return Nones as if keys don't exist
    mock_pipeline.execute.return_value = [None] * 8
    
    current_time = datetime(2026, 8, 10, 10, 0, 0, tzinfo=UTC)
    
    fv = await compute_windowed_features("hostA:userA:1.1.1.1", mock_redis, current_time)
    
    assert isinstance(fv, FeatureVector)
    assert fv.event_count_1m == 0.0
    assert fv.failed_auth_ratio == 0.0
    assert fv.distinct_dest_ports == 0.0
    assert fv.dest_ip_fanout == 0.0
    assert fv.bytes_transferred == 0.0
    assert fv.tod_zscore == 0.0
    assert fv.geo_velocity_kmh == 0.0


@pytest.mark.asyncio
async def test_compute_windowed_features_populated():
    """Test feature extraction when Redis has data."""
    mock_redis = MagicMock()
    mock_pipeline = AsyncMock()
    mock_redis.pipeline.return_value = mock_pipeline
    
    # [1m_cnt, 5m_cnt, 1h_cnt, fail_cnt, total_cnt, ports, ips, bytes]
    mock_pipeline.execute.return_value = [5, 12, 45, 3, 10, 4, 2, 1024]
    
    current_time = datetime(2026, 8, 10, 10, 0, 0, tzinfo=UTC)
    
    fv = await compute_windowed_features("hostB:userB:2.2.2.2", mock_redis, current_time)
    
    assert fv.event_count_1m == 5.0
    assert fv.event_count_5m == 12.0
    assert fv.event_count_1h == 45.0
    assert fv.failed_auth_ratio == 0.3  # 3 / 10
    assert fv.distinct_dest_ports == 4.0
    assert fv.dest_ip_fanout == 2.0
    assert fv.bytes_transferred == 1024.0
