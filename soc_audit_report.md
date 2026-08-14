# SOC Triager — Codebase Audit Report

**Repo:** `SKYLINE217/AI-driven---SOC`  
**Audited:** August 2026 (current `main`)  
**Scope:** All Python backend, React frontend, YAML rules, test suite. README excluded.

---

## Executive Summary

The architecture is solid and well-thought-out: ECS-normalized events, a dual-model ensemble (Isolation Forest + Autoencoder), deterministic triage, hash-chained ledger, and layered sanitization. The bones are good. However, there are **2 critical correctness bugs that silently produce wrong output**, **2 security issues that need remediation before any deployment**, and **4 missing template files** that cause silent fallback to a generic playbook. The frontend is almost entirely mocked out and disconnected from the CLI backend.

---

## Critical Issues

### C-1 · Feature State Never Reset Between Ingest Runs
**File:** `backend/ml/feature_engineering.py`, `backend/soc_triager.py`

Seven module-level data structures — `_event_times`, `_fail_times`, `_dest_ports`, `_dest_ips`, `_byte_totals`, `_last_geo`, `_hourly_counts` — persist across the entire Python process lifetime. `cmd_ingest` never calls `reset_state()` before scoring. Running `ingest` twice in a session (or processing a second log file) cross-contaminates feature windows: entity event counts from file A bleed into file B's sliding window calculations.

This is a **silent correctness bug** — no crash, no warning, wrong anomaly scores. The `_hourly_counts` array additionally never gets reset (even `reset_state()` sets it back to `1.0`, but that's never called from the CLI), so the `tod_zscore` computation converges toward zero for any long run.

**Fix:** Call `feature_engineering.reset_state()` at the top of `cmd_ingest`, before `score_events()`.

---

### C-2 · Training-vs-Scoring Feature Distribution Mismatch
**File:** `backend/ml/train.py` vs `backend/ml/feature_engineering.py`

`train.py` manufactures features like this:
```python
features['event_count_5m'] = features['event_count_1m'] * 5
features['event_count_1h'] = features['event_count_1m'] * 60
features['failed_auth_ratio'] = 0.0  # always zero during training
features['dest_ip_fanout'] = 0.0     # always zero during training
features['tod_zscore'] = 0.0         # always zero during training
features['geo_velocity_kmh'] = 0.0   # always zero during training
```

At score time, `feature_engineering.extract_features()` computes these from real sliding windows with completely different distributions. The model was trained on synthetic, highly correlated (5m = 1m×5) data with four features locked to zero. Any real event will push four features into unseen space. The ensemble's anomaly threshold (0.40) was presumably chosen against this corrupted baseline, making all calibration meaningless.

**Fix:** The training `extract_features()` function must produce the same distribution as the runtime one — either replay real events through `feature_engineering.extract_features()` to build training vectors, or at minimum remove the synthetic multiplier and use realistic sampled distributions for all 9 features.

---

## Security Issues

### S-1 · `eval()` on YAML Rule Conditions
**File:** `backend/mitre/mapping_engine.py:155`

```python
if eval(rule["condition"], {"__builtins__": {}}, context):
```

The comment says "Basic eval is fine here since rules are internal config." That's a meaningful risk claim worth examining. The `__builtins__: {}` sandbox is not watertight — known Python sandbox escapes exist via `().__class__.__bases__[0].__subclasses__()` or attribute chains, though the local context dict limits how much attacker-controlled data reaches it. The real concern is **file integrity**: if `rules.yaml` is compromised (supply chain, CI misconfiguration, lateral movement to the deployment host), this becomes arbitrary code execution.

Since all current conditions are simple comparisons (`>`, `<`, `in`, `and`, `==`), they can trivially be replaced with a data-driven evaluator with zero `eval()`.

**Fix:** Parse conditions into an AST or implement a tiny rule DSL:
```python
# Example: replace eval with a safe comparator dict
OPS = {">": operator.gt, "<": operator.lt, "==": operator.eq, "in": lambda a, b: a in b}
```
Or use `ast.literal_eval` for values and a whitelist of allowed operators.

---

### S-2 · `pickle.load()` for Isolation Forest Model
**File:** `backend/ml/scorer.py:20`

```python
_if_model = pickle.load(f)  # isolation_forest.pkl
```

The autoencoder correctly uses `torch.load(..., weights_only=True)`. The sklearn model does not get the same treatment — `pickle` deserialization is **arbitrary code execution** if the model file is tampered. In a SOC tool processing untrusted logs, this is a meaningful attack surface (an attacker who can write to the model directory wins).

**Fix:** Use `joblib.load()` (safer for sklearn models, better error messages) and/or validate a SHA-256 checksum of the `.pkl` file against a pinned value before loading. Long term, serialize the IF model as JSON parameters rather than pickle.

---

## Medium Issues

### M-1 · Top-Feature Contribution Scores Are Meaningless
**File:** `backend/ml/scorer.py:51`

```python
contributions = list(zip(feature_names, np.abs(features - 0.5)))
```

This is deviation from the midpoint of `[0, 1]`, not model-derived importance. A feature with value `0.9` contributes `0.4` regardless of whether the Isolation Forest actually split on it. The top-3 features shown in incident rationales (`"event_count_1m=0.8743"`) are meaningless as explanations and could actively mislead analysts.

**Fix:**
- For Isolation Forest: use `sklearn`'s `estimators_` to compute mean path length contribution per feature.
- For Autoencoder: use per-feature reconstruction error `(x - reconstructed)**2` instead of the global MSE.

---

### M-2 · 4 Missing Playbook Templates (Silent Fallback)
**File:** `backend/artifacts/playbook_renderer.py`

`TECHNIQUE_TEMPLATE_MAP` references 9 templates. Only 5 exist on disk plus the generic fallback:

| Technique | Template | Status |
|-----------|----------|--------|
| T1046 | `port_scan_block.yml.j2` | **MISSING** |
| T1055 | `process_injection_isolation.yml.j2` | **MISSING** |
| T1078 | `impossible_travel_lockout.yml.j2` | **MISSING** |
| T1059 | `scripting_interpreter_block.yml.j2` | **MISSING** |

The renderer catches the `TemplateNotFound` exception and silently falls back to `generic_block.yml.j2`. An analyst gets a generic "block source IP" playbook for process injection — completely wrong containment steps, no error raised.

**Fix:** Either create the 4 missing templates or raise explicitly when a mapped technique has no template, so the gap surfaces in CI rather than silently in production.

---

### M-3 · `autoescape=True` on a Markdown Template
**File:** `backend/artifacts/report_generator.py:91`

```python
_jinja_env = Environment(loader=BaseLoader(), autoescape=True)
```

`autoescape=True` HTML-escapes `<`, `>`, `&` as `&lt;`, `&gt;`, `&amp;`. The template produces `.md` files, not HTML. Every IP address comparison, CIDR notation, or log field containing `<` or `>` will be corrupted in the output report. Example: `anomaly score > 0.40` becomes `anomaly score &gt; 0.40`.

The log sanitization in `sanitize_log_content()` already handles injection prevention. Autoescape is the wrong tool here.

**Fix:** `autoescape=False` (or use `select_autoescape(["html", "htm"])` to explicitly scope it). Rely on `sanitize_log_content()` for safety, which is already applied to all evidence before rendering.

---

### M-4 · f-string SQL Fragment in `list_incidents`
**File:** `backend/services/incident_service.py:101`

```python
where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
rows = conn.execute(
    f"SELECT * FROM incidents {where} ORDER BY created_at DESC LIMIT ?",
    params
)
```

The `clauses` list is built from hardcoded strings (`"status = ?"`, `"severity = ?"`), so the current callers can't inject through `status` or `severity`. But the `where` fragment is structurally injectable — if this function is later extended (add a `text_search` param, a date filter), a developer might append a raw clause without noticing the f-string pattern. The values are already parameterized; only the clause names need hardening.

**Fix:** Replace the f-string with an explicit allowlist:
```python
VALID_FILTERS = {"status": "status = ?", "severity": "severity = ?"}
clauses = [VALID_FILTERS[k] for k in filters if k in VALID_FILTERS]
```

---

## Low / Design Issues

### D-1 · Evaluation Reports Synthetic Metrics as Real
**File:** `backend/ml/evaluate.py`, `docs/EVAL_RESULTS.md`

`cmd_evaluate` always calls `generate_synthetic_evaluation()`, which produces metrics from a seeded beta distribution — not from running the trained models against CICIDS2017. The printed/reported numbers (Precision: 84.7%, Recall: 93.1%, ROC-AUC: 0.973) are not model performance — they are the shape parameters of a synthetic distribution chosen to look good.

This is documented inline but the `EVAL_RESULTS.md` presents these as factual metrics without a visible disclaimer. If this document is used to justify deployment, it's misleading.

**Fix:** When CICIDS data is present, run the actual trained model through `predict()` and compute real metrics. Gate `generate_synthetic_evaluation()` clearly behind a `--synthetic` flag, or add a visible `[SYNTHETIC - NOT REAL MODEL OUTPUT]` header to the report.

---

### D-2 · `config.py` Base Dir Points to `backend/`, Not Repo Root
**File:** `backend/config.py`

```python
BASE_DIR = Path(__file__).parent  # → backend/
DATA_DIR  = BASE_DIR / "data"     # → backend/data/
MITRE_STIX = DATA_DIR / "mitre" / "enterprise-attack-v15.1.json"
```

The actual MITRE STIX file lives at `data/mitre/` (repo root, 42MB). The CICIDS CSV files would also need to go to `backend/data/cicids2017/`. The env vars work around this, but the defaults silently point nowhere without an error message — the user just gets "MITRE rule engine unavailable" fallback behavior with no guidance.

**Fix:** Default `DATA_DIR` to `Path(__file__).parent.parent / "data"` (repo root), or add a startup check that warns explicitly when STIX or model files are absent.

---

### D-3 · Frontend Is Substantially Mocked
**File:** `frontend/src/pages/IncidentDetail.tsx`, `frontend/src/data/`

Four of the five `IncidentDetail` tabs are explicitly placeholders:
```jsx
{tab === "alerts"   && <div>{incident.alert_count} associated alerts (simulated)</div>}
{tab === "playbook" && <div>Playbook draft logic goes here.</div>}
{tab === "graph"    && <div>Graph visualization placeholder.</div>}
{tab === "ledger"   && <div>Ledger history placeholder.</div>}
```

The frontend uses seed data from `seedIncidents.ts / seedPlaybooks.ts / seedRules.ts`. The `api_client.ts` has all the endpoint methods defined, but there is no running API server — the backend is a pure CLI, not FastAPI or any HTTP server. The `RoleGate` component does RBAC in the browser with no backend enforcement.

This is not a bug in what exists — but it's a material gap between the docs/plan and the delivered system.

---

### D-4 · `api_legacy/` Module Conflicts With Real Service in Tests
**File:** `backend/api_legacy/incident_service.py`

Tests import from `api_legacy` (in-memory store). The real incident service at `backend/services/incident_service.py` (SQLite-backed) has **no tests**. If a developer writes a test for the real service, they'll import from the wrong module by convention. The legacy module also leaks global `_alerts`, `_incidents`, `_ledger` state between tests unless explicitly cleared.

---

## Test Coverage Gaps

| Module | Covered |
|--------|---------|
| `ingestion/normalizers/` (all 4) | ✅ |
| `mitre/alert_clustering.py` | ✅ |
| `mitre/mapping_engine.py` | ✅ |
| `ml/feature_engineering.py` | ✅ |
| `api_legacy/incident_service.py` | ✅ |
| `artifacts/` (report, graph, playbook, sanitizers, ioc_validators) | ❌ |
| `ml/scorer.py` | ❌ |
| `ml/train.py` | ❌ |
| `services/triage.py` | ❌ |
| `services/incident_service.py` (real SQLite version) | ❌ |
| `ingestion/file_ingestor.py` | ❌ |
| `database.py` | ❌ |

The untested `artifacts/` path is particularly risky because it handles security-sensitive sanitization of log content before rendering. `sanitizers.py` and `ioc_validators.py` have no tests to verify that injection payloads are actually blocked.

---

## Priority Summary

| # | Issue | Severity | Effort |
|---|-------|----------|--------|
| C-1 | Feature state not reset between ingest runs | **Critical** | 1 line |
| C-2 | Train/score feature distribution mismatch | **Critical** | Medium |
| S-1 | `eval()` on YAML rule conditions | **High** | Medium |
| S-2 | `pickle.load()` for model deserialization | **High** | Small |
| M-1 | Contribution scores are meaningless | Medium | Medium |
| M-2 | 4 missing playbook templates (silent fallback) | Medium | Small |
| M-3 | `autoescape=True` corrupts Markdown output | Medium | 1 line |
| M-4 | f-string SQL fragment in `list_incidents` | Medium | Small |
| D-1 | Eval reports synthetic metrics as real | Low | Small |
| D-2 | Config base dir mispoints | Low | Small |
| D-3 | Frontend is substantially mocked | Design | Large |
| D-4 | Legacy API module conflicts with real service | Low | Small |

---

*Audit performed against codebase as-cloned. No README referenced.*
