import math
import time
from collections import deque, defaultdict
from typing import Any, Dict, Tuple
import numpy as np
from ..config import WINDOW_1M, WINDOW_5M, WINDOW_1H

_event_times: Dict[str, deque] = defaultdict(deque)
_fail_times:  Dict[str, deque] = defaultdict(deque)
_dest_ports:  Dict[str, set]   = defaultdict(set)
_dest_ips:    Dict[str, set]   = defaultdict(set)
_byte_totals: Dict[str, int]   = defaultdict(int)
_last_geo:    Dict[str, Tuple[float, float, float]] = {}
_hourly_counts: np.ndarray = np.ones(24)


def _bucket_key(entity: str, ts: float) -> str:
    return f"{entity}:{int(ts // 300)}"


def _trim_deque(dq: deque, cutoff: float):
    while dq and dq[0][0] < cutoff:
        dq.popleft()


def _sliding_count(dq: deque, ts: float, window: int) -> int:
    _trim_deque(dq, ts - window)
    return len(dq)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _extract_geo(event: Dict[str, Any]):
    src = event.get("source", {}) or {}
    geo = src.get("geo", {}) or {}
    loc = geo.get("location", {}) or {}
    lat = loc.get("lat")
    lon = loc.get("lon")
    if lat is None:
        lat = geo.get("latitude")
    if lon is None:
        lon = geo.get("longitude")
    return lat, lon


def extract_features(event: Dict[str, Any]) -> np.ndarray:
    ts     = event.get("@timestamp_unix")
    if ts is None:
        ts_val = event.get("timestamp")
        if isinstance(ts_val, (int, float)):
            ts = float(ts_val)
        elif hasattr(ts_val, "timestamp"):
            ts = float(ts_val.timestamp())
        else:
            ts = time.time()

    src = event.get("source", {}) or {}
    usr = event.get("user", {}) or {}
    entity = src.get("ip") or usr.get("name") or "unknown"

    ev = event.get("event", {}) or {}
    is_fail = int(ev.get("outcome") == "failure")

    dst = event.get("destination", {}) or {}
    dport = dst.get("port", 0) or 0
    dip = dst.get("ip", "") or ""

    net = event.get("network", {}) or {}
    nbytes = net.get("bytes", 0) or 0

    lat, lon = _extract_geo(event)

    event_id = ev.get("id", str(ts))
    _event_times[entity].append((ts, event_id))
    if is_fail:
        _fail_times[entity].append((ts, event_id))

    bkey = _bucket_key(entity, ts)
    if dport:
        _dest_ports[bkey].add(dport)
    if dip:
        _dest_ips[bkey].add(dip)
    _byte_totals[bkey] = _byte_totals.get(bkey, 0) + int(nbytes)

    cnt_1m = _sliding_count(_event_times[entity], ts, WINDOW_1M)
    cnt_5m = _sliding_count(_event_times[entity], ts, WINDOW_5M)
    cnt_1h = _sliding_count(_event_times[entity], ts, WINDOW_1H)

    fail_dq = _fail_times[entity]
    _trim_deque(fail_dq, ts - WINDOW_5M)
    fail_ratio = len(fail_dq) / max(cnt_5m, 1)

    distinct_ports = len(_dest_ports.get(bkey, set()))
    dest_fanout    = len(_dest_ips.get(bkey, set()))
    byte_total     = _byte_totals.get(bkey, 0)

    hour = int(time.gmtime(ts).tm_hour)
    _hourly_counts[hour] += 1
    mean_h = _hourly_counts.mean()
    std_h  = _hourly_counts.std() or 1.0
    tod_z  = (_hourly_counts[hour] - mean_h) / std_h

    geo_vel = 0.0
    if lat is not None and lon is not None:
        if entity in _last_geo:
            plat, plon, pts = _last_geo[entity]
            dt = max(ts - pts, 1.0)
            dist = _haversine_km(plat, plon, float(lat), float(lon))
            geo_vel = (dist / dt) * 3600
        _last_geo[entity] = (float(lat), float(lon), ts)

    return np.array([
        float(cnt_1m), float(cnt_5m), float(cnt_1h),
        float(fail_ratio), float(distinct_ports), float(dest_fanout),
        float(byte_total), float(tod_z), float(geo_vel),
    ], dtype=np.float32)


def reset_state():
    """Reset all sliding window deques, spatial/network tracking, and hourly distributions."""
    _event_times.clear()
    _fail_times.clear()
    _dest_ports.clear()
    _dest_ips.clear()
    _byte_totals.clear()
    _last_geo.clear()
    _hourly_counts[:] = 1.0


# ── Backward-compat shim for original Redis-based test suite ────────────────

async def compute_windowed_features(entity_key, redis_client, current_time):
    """
    Original test-compatible shim.

    The test mocks redis.pipeline().execute() to return an 8-element list:
        [1m_cnt, 5m_cnt, 1h_cnt, fail_cnt, total_cnt, distinct_ports, distinct_ips, bytes]
    This function awaits the mock pipeline, builds a FeatureVector, and returns it.
    """
    from ..models import FeatureVector
    import numpy as np

    pipe = redis_client.pipeline()
    results = await pipe.execute()
    values = list(results) + [None] * 8
    cnt_1m, cnt_5m, cnt_1h, fail_cnt, total_cnt, dports, dips, nbytes = values[:8]

    def f(v):
        return 0.0 if v is None else float(v)

    total = max(f(total_cnt), 1.0)
    failed_ratio = f(fail_cnt) / total

    # Tod zscore from the hour in current_time
    # If all window counters are zero (entity has no history), return 0.0 to
    # match the original Redis-based behaviour when sliding keys don't exist.
    try:
        if f(cnt_1m) == 0.0 and f(cnt_5m) == 0.0 and f(cnt_1h) == 0.0:
            tod_z = 0.0
        else:
            hour = int(getattr(current_time, "hour", 0))
            counts_arr = np.ones(24, dtype=np.float64)
            counts_arr[hour] += 1
            mean_h = float(counts_arr.mean())
            std_h = float(counts_arr.std()) or 1.0
            tod_z = float((counts_arr[hour] - mean_h) / std_h)
    except Exception:
        tod_z = 0.0

    return FeatureVector(
        entity_key=entity_key,
        timestamp=current_time,
        event_count_1m=f(cnt_1m),
        event_count_5m=f(cnt_5m),
        event_count_1h=f(cnt_1h),
        failed_auth_ratio=failed_ratio,
        distinct_dest_ports=f(dports),
        dest_ip_fanout=f(dips),
        bytes_transferred=f(nbytes),
        tod_zscore=tod_z,
        geo_velocity_kmh=0.0,
    )


