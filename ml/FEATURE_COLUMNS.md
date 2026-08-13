# Feature Columns — ML Feature Engineering Reference

## FeatureVector Fields (9 features)

These features are computed per entity `(host:user:source_ip)` over sliding time windows
and stored in Redis (hot) and TimescaleDB (cold).

| # | Feature Name | Window | Source | Description |
|---|---|---|---|---|
| 1 | `event_count_1m` | 1 min | Redis ZADD | Total events from this entity in the last 60 seconds |
| 2 | `event_count_5m` | 5 min | Redis ZADD | Total events from this entity in the last 5 minutes |
| 3 | `event_count_1h` | 1 hour | Redis ZADD | Total events from this entity in the last hour |
| 4 | `failed_auth_ratio` | 5 min | Redis HSET | Ratio of failed auth events to total auth events |
| 5 | `distinct_dest_ports` | 5 min | Redis PFADD (HLL) | Count of unique destination ports (port scan signal) |
| 6 | `dest_ip_fanout` | 5 min | Redis PFADD (HLL) | Count of unique destination IPs (lateral movement signal) |
| 7 | `bytes_transferred` | 5 min | Redis INCRBY | Total bytes transferred (exfiltration signal) |
| 8 | `tod_zscore` | Current hour | TimescaleDB historical | Z-score deviation from this entity's historical time-of-day pattern |
| 9 | `geo_velocity_kmh` | Last 2 events | `entities` table | Speed between last two geolocated events (impossible travel) |

## CICIDS2017 Column Mapping

The CICIDS2017 dataset columns are mapped to our FeatureVector as follows during training:

| CICIDS2017 Column | → FeatureVector Field | Notes |
|---|---|---|
| `Flow Duration` | (used in windowed computation) | Microseconds |
| `Total Fwd Packets` | `event_count_*` (proxy) | Summed over window |
| `Total Backward Packets` | (included in event count) | — |
| `Flow Bytes/s` | `bytes_transferred` (proxy) | Converted from rate to window total |
| `Destination Port` | `distinct_dest_ports` (aggregated) | HLL count of unique ports |
| `Fwd Packet Length Mean` | (included in bytes computation) | — |
| `Flow IAT Mean` | (used in temporal features) | Inter-arrival time |
| `Label` | Ground truth label | BENIGN vs attack class |

### Attack Labels in CICIDS2017

| Label | Expected High Features | MITRE Mapping |
|---|---|---|
| `SSH-Patator` | `event_count_1m`, `failed_auth_ratio` | T1110 (Brute Force) |
| `FTP-Patator` | `event_count_1m`, `failed_auth_ratio` | T1110 (Brute Force) |
| `DDoS` | `event_count_1m`, `bytes_transferred` | T1498 (Network DoS) |
| `PortScan` | `distinct_dest_ports` | T1046 (Network Service Scanning) |
| `Bot` | `dest_ip_fanout`, `event_count_1h` | T1071 (Application Layer Protocol) |
| `Infiltration` | `dest_ip_fanout`, `bytes_transferred` | T1041 (Exfiltration Over C2) |
| `Web Attack – Brute Force` | `event_count_1m`, `failed_auth_ratio` | T1110 (Brute Force) |
| `Web Attack – XSS` | `event_count_5m` | T1059 (Command & Scripting) |
| `Web Attack – Sql Injection` | `event_count_5m` | T1190 (Exploit Public-Facing App) |

## Notes

- All features default to `0.0` for new entities with no history
- The `to_array()` method on `FeatureVector` returns features in the exact order listed above
- Models (IsolationForest and Autoencoder) expect this exact order and count (9 features)
- Feature scaling is applied inside the scoring service, not at computation time
