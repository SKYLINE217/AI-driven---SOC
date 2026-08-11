import time
from datetime import UTC, datetime
from typing import Optional

from backend.models import FeatureVector


async def compute_windowed_features(
    entity_key: str,
    redis_client,
    current_time: Optional[datetime] = None
) -> FeatureVector:
    """
    Computes the 9-dimensional FeatureVector for a given entity by reading
    sliding window aggregations from Redis.
    """
    if current_time is None:
        current_time = datetime.now(UTC)
        
    now_ts = current_time.timestamp()
    
    # Run all redis commands in a pipeline for performance
    pipeline = redis_client.pipeline()
    
    # 1. Event counts (ZCOUNT over different windows)
    pipeline.zcount(f"events:{entity_key}:1m", now_ts - 60, "+inf")
    pipeline.zcount(f"events:{entity_key}:5m", now_ts - 300, "+inf")
    pipeline.zcount(f"events:{entity_key}:1h", now_ts - 3600, "+inf")
    
    # 2. Failed auth ratio (GET fail and total)
    pipeline.get(f"auth:{entity_key}:fail")
    pipeline.get(f"auth:{entity_key}:total")
    
    # 3. Unique destinations (HyperLogLog PFCOUNT)
    pipeline.pfcount(f"ports:{entity_key}:5m")
    pipeline.pfcount(f"dests:{entity_key}:5m")
    
    # 4. Bytes transferred (GET)
    pipeline.get(f"bytes:{entity_key}:5m")
    
    # Execute pipeline
    results = await pipeline.execute()
    
    # Parse results
    event_count_1m = float(results[0] or 0.0)
    event_count_5m = float(results[1] or 0.0)
    event_count_1h = float(results[2] or 0.0)
    
    fail_count = float(results[3] or 0.0)
    total_count = float(results[4] or 0.0)
    failed_auth_ratio = (fail_count / total_count) if total_count > 0 else 0.0
    
    distinct_dest_ports = float(results[5] or 0.0)
    dest_ip_fanout = float(results[6] or 0.0)
    bytes_transferred = float(results[7] or 0.0)
    
    # 5. DB features (mocked to 0.0 for now, as they require TimescaleDB)
    tod_zscore = 0.0
    geo_velocity_kmh = 0.0
    
    return FeatureVector(
        entity_key=entity_key,
        timestamp=current_time,
        event_count_1m=event_count_1m,
        event_count_5m=event_count_5m,
        event_count_1h=event_count_1h,
        failed_auth_ratio=failed_auth_ratio,
        distinct_dest_ports=distinct_dest_ports,
        dest_ip_fanout=dest_ip_fanout,
        bytes_transferred=bytes_transferred,
        tod_zscore=tod_zscore,
        geo_velocity_kmh=geo_velocity_kmh
    )
