# SOC Triager — Instructions for Engineer A
## ML / Data / Backend Lead

> **Your role:** You own the intelligence core of the system — everything that makes raw logs become meaningful, prioritized, MITRE-mapped incidents. Engineer B owns the platform that surfaces your outputs.
>
> **Daily rhythm:** 09:00 standup (15 min) · 13:00 integration checkpoint (20 min) · 17:30 end-of-day deploy verification (15 min)
>
> **Golden rule:** Never write code that doesn't have a test. Never push a model that isn't registered in MLflow. Never let a log injection surface into a template unvalidated.

---

## Day 1 — Architecture Lock, Data Ingestion, Synthetic Data

### Morning (09:00–12:00)

**1. Attend the architecture kickoff (shared, 09:00–10:30)**
- Lock the ECS event schema from `system-architecture.md §3.2` — this is your contract with Engineer B; once agreed, don't change field names without a sync
- Agree on the repo monorepo structure: `/backend /frontend /infra /data /docs`
- Confirm your Anthropic API key works end-to-end: write a single `hello_claude.py` script that calls `claude-sonnet-4-6` with a trivial prompt and prints the response. Run it. If it fails, fix it before writing any other code.

**2. Clone the repo and set up your Python environment**

```bash
cd soc-triager/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt --require-hashes
cp .env.example .env   # fill in your secrets
```

**3. Download and inspect the datasets**

```bash
# CICIDS2017 — download Wednesday (working hours) and Friday (DDoS/PortScan) subsets
# from https://www.unb.ca/cic/datasets/ids-2017.html
# Place in /data/cicids2017/

# Elastic sample security logs
# from https://www.elastic.co/guide/en/kibana/current/sample-data.html
# Place in /data/elastic_samples/

# Inspect the first 5 rows of each CICIDS2017 file
python -c "
import pandas as pd
df = pd.read_csv('data/cicids2017/Wednesday-workingHours.pcap.IANA_labels.csv', nrows=5)
print(df.columns.tolist())
print(df.head())
"
```

Document every column you plan to use from CICIDS2017 in `backend/ml/FEATURE_COLUMNS.md`.

**4. Write the source normalizers**

For each source type, write a function in `backend/ingestion/normalizers/`:

```python
# syslog_normalizer.py
from backend.models import NormalizedEvent

def normalize_syslog(raw_line: str) -> NormalizedEvent:
    """Parse RFC5424 syslog line into ECS NormalizedEvent."""
    # ... parse timestamp, hostname, program, message
    return NormalizedEvent(
        timestamp=...,
        event=EventInfo(kind="event", action=..., outcome=...),
        source=SourceInfo(ip=...),
        host=HostInfo(name=...),
        log=LogInfo(source_type="syslog", raw=raw_line[:1000])
    )
```

Write at least 3 unit tests per normalizer in `backend/tests/test_normalizers.py`:
- Happy path with a valid sample line
- Line with missing fields (should not raise — use defaults)
- Line with injected special characters (should not raise)

**5. Write the synthetic data generators**

```bash
# backend/ingestion/generators/
# cloudtrail_generator.py — generates synthetic AWS CloudTrail JSON with injected attack patterns
# auth_log_generator.py — generates Linux auth.log with injected brute force sequences
```

The brute-force sequence: generate 20 `Failed password` lines from the same source IP within 90 seconds, targeting 4 different usernames. This will be your deterministic demo scenario.

**6. Stand up MLflow**

```bash
docker compose up -d mlflow
# MLflow UI available at http://localhost:5000

# Verify with a trivial run
python -c "
import mlflow
mlflow.set_tracking_uri('http://localhost:5000')
with mlflow.start_run(run_name='baseline_test'):
    mlflow.log_param('model', 'test')
    mlflow.log_metric('accuracy', 0.99)
print('MLflow OK')
"
```

### Afternoon (13:00–17:30)

**7. Integration checkpoint with Engineer B (13:00)**
- Confirm ECS schema is agreed
- Confirm Engineer B's Redpanda topics are created: `raw.syslog`, `raw.cloudtrail`, `raw.auth`, `raw.cicids`
- Agree on the Pydantic models for `NormalizedEvent`, `FeatureVector`, `ScoreResponse` — these are the interfaces between your code and the Faust worker

**8. Wire the Faust normalizer agent**

The Faust app is owned by Engineer B structurally, but you provide the normalizer functions it calls. Make sure your normalizers are importable from `backend/ingestion/normalizers/__init__.py` with a clean interface:

```python
from backend.ingestion.normalizers import get_normalizer
normalizer = get_normalizer(source_type="auth")  # returns the right function
ecs_event = normalizer(raw_line)
```

**End of Day 1 checklist:**
- [ ] All four normalizers written and unit-tested
- [ ] Synthetic CloudTrail and auth.log generators producing valid output
- [ ] MLflow tracking server running and accessible
- [ ] Your trivial Claude API call works
- [ ] ECS schema agreed with Engineer B
- [ ] Normalizer interface importable by Faust worker (confirm with Engineer B)

---

## Day 2 — Feature Engineering, ML Training, Evaluation Harness

### Morning (09:00–13:00)

**1. Feature engineering**

In `backend/ml/feature_engineering.py`, implement `compute_windowed_features(entity_key, redis_client)`:

| Feature | Window | Redis key pattern |
|---|---|---|
| `event_count_1m` | 1 min | `events:{entity_key}:1m` (sorted set by timestamp) |
| `event_count_5m` | 5 min | `events:{entity_key}:5m` |
| `event_count_1h` | 1 h | `events:{entity_key}:1h` |
| `failed_auth_ratio` | 5 min | `auth:{entity_key}:fail` and `auth:{entity_key}:total` |
| `distinct_dest_ports` | 5 min | `ports:{entity_key}:5m` (HyperLogLog) |
| `dest_ip_fanout` | 5 min | `dests:{entity_key}:5m` (HyperLogLog) |
| `bytes_transferred` | 5 min | `bytes:{entity_key}:5m` (counter) |
| `tod_zscore` | current hour vs. historical baseline | computed from TimescaleDB |
| `geo_velocity_kmh` | last event location vs. current | stored in `entities` table |

Return a `FeatureVector` Pydantic model with all features. Default to 0 for missing keys (new entity with no history).

**2. Prepare the CICIDS2017 training split**

```python
# backend/ml/train.py
import pandas as pd
from sklearn.model_selection import train_test_split

# Load Wednesday (mostly benign) for training the "normal" baseline
df_benign = pd.read_csv('data/cicids2017/Wednesday-workingHours.pcap.IANA_labels.csv')
df_benign = df_benign[df_benign[' Label'] == 'BENIGN']

# Load Friday attack days for evaluation
df_attacks = pd.read_csv('data/cicids2017/Friday-WorkingHours-Afternoon-DDos.pcap_IANA_labels.csv')

# Map CICIDS2017 columns to your FeatureVector fields
# Document the mapping in backend/ml/FEATURE_COLUMNS.md
```

**3. Train Isolation Forest**

```python
from sklearn.ensemble import IsolationForest
import mlflow

with mlflow.start_run(run_name="isolation_forest_v1"):
    model = IsolationForest(n_estimators=200, contamination='auto', random_state=42)
    model.fit(X_train)  # X_train = benign feature vectors

    # Evaluate on held-out attack data
    y_pred = model.predict(X_test)  # -1 = anomaly, 1 = normal
    y_true = (labels_test != 'BENIGN').astype(int)

    from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
    precision = precision_score(y_true, (y_pred == -1).astype(int))
    recall = recall_score(y_true, (y_pred == -1).astype(int))

    mlflow.log_params({"n_estimators": 200, "contamination": "auto"})
    mlflow.log_metrics({"precision": precision, "recall": recall, "f1": f1_score(...)})
    mlflow.sklearn.log_model(model, "isolation_forest")

print(f"Precision: {precision:.3f}, Recall: {recall:.3f}")
# Target: precision >= 0.75, recall >= 0.90
```

### Afternoon (13:00–17:30)

**4. Train the Autoencoder**

```python
# backend/ml/autoencoder.py
import torch
import torch.nn as nn

class Autoencoder(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 8)
        )
        self.decoder = nn.Sequential(
            nn.Linear(8, 16), nn.ReLU(),
            nn.Linear(16, 32), nn.ReLU(),
            nn.Linear(32, input_dim)
        )
    def forward(self, x):
        return self.decoder(self.encoder(x))

# Train on benign-only data; log training curves and reconstruction-error distribution to MLflow
# Anomaly score = MSE reconstruction error, converted to a percentile against the benign distribution
```

**5. Build the ensemble and tune the threshold**

```python
def ensemble_score(if_score: float, ae_score: float) -> float:
    return 0.6 * if_score + 0.4 * ae_score

# Produce a precision-recall curve across threshold values
# Pick the threshold that achieves recall >= 0.90 at precision >= 0.75
# Document the choice in backend/ml/THRESHOLD_DECISION.md
```

**6. Register both models in MLflow**

```python
mlflow.register_model("runs:/<run_id>/isolation_forest", "isolation_forest")
mlflow.register_model("runs:/<run_id>/autoencoder", "autoencoder")
# Transition both to "production" stage in the MLflow UI or via API
```

**End of Day 2 checklist:**
- [ ] `FeatureVector` model implemented with all 9+ features
- [ ] Isolation Forest trained, precision ≥ 0.75, recall ≥ 0.90
- [ ] Autoencoder trained, reconstruction-error distribution logged to MLflow
- [ ] Ensemble threshold documented in `THRESHOLD_DECISION.md`
- [ ] Both models registered in MLflow at "production" stage
- [ ] Confirm with Engineer B: Scoring API loads your models from MLflow correctly

---

## Day 3 — MITRE Mapping + LLM Triage Client

### Morning (09:00–13:00)

**1. Set up the MITRE ATT&CK corpus**

```python
# backend/mitre/mapping_engine.py
from mitreattack.stix20 import MitreAttackData

attack = MitreAttackData("data/mitre/enterprise-attack-v15.1.json")

def get_technique(technique_id: str) -> dict:
    technique = attack.get_technique_by_attack_id(technique_id)
    return {
        "id": technique_id,
        "name": technique.name,
        "tactic": technique.kill_chain_phases[0].phase_name,
        "description": technique.description,
        ...
    }
```

**2. Write the heuristic candidate rules (`backend/mitre/rules.yaml`)**

Write at least 15 rules covering:
- Brute force (SSH, RDP, HTTP auth) → T1110.x
- Port scan → T1046
- DDoS → T1498
- Lateral movement (SMB, RDP) → T1021.x
- Privilege escalation → T1548.x
- Data exfiltration (large outbound transfer) → T1041
- Impossible travel (geo-velocity) → T1078
- Process injection signals → T1055
- Suspicious process lineage → T1059

Test the rule engine with `pytest backend/tests/test_mitre_mapping.py` using synthetic event fixtures.

### Afternoon (13:00–17:30)

**3. Build the LLM triage client (`backend/llm/triage_client.py`)**

```python
import anthropic
from pydantic import BaseModel, Field
from typing import Literal

client = anthropic.Anthropic()

class TriageResult(BaseModel):
    technique_id: str  # must be from candidate list
    technique_name: str
    tactic: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=500)
    severity: Literal["critical", "high", "medium", "low"]
    recommended_immediate_action: str = Field(max_length=300)

def triage_event_cluster(
    events: list[dict],
    anomaly_score: float,
    top_features: list[dict],
    candidate_technique_ids: list[str]
) -> TriageResult:
    prompt = build_triage_prompt(events, anomaly_score, top_features, candidate_technique_ids)

    for attempt in range(3):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            result = TriageResult.model_validate_json(response.content[0].text)
            if result.technique_id not in candidate_technique_ids:
                raise ValueError("Technique ID not in candidate list")
            log_llm_call(response, len(events))
            return result
        except Exception as e:
            if attempt == 2:
                raise
            continue
```

Write unit tests using mock responses (don't hit the real API in unit tests — use `unittest.mock.patch`). Write one integration test using a real API call with a small, deterministic fixture.

**End of Day 3 checklist:**
- [ ] MITRE mapping engine integrated with pinned corpus
- [ ] 15+ heuristic rules written and tested
- [ ] LLM triage client implemented with retry, schema validation, and logging
- [ ] Unit tests passing with mocked Claude responses
- [ ] Integration test passing with real Claude call
- [ ] Confirm with Engineer B: alert clustering logic in the incident correlation service is compatible with your `TriageResult` schema

---

## Day 4 — Artifact Generation + Evaluation Report

### Morning (09:00–13:00)

**1. Markdown incident report generator (`backend/artifacts/report_generator.py`)**

The Jinja2 template (`templates/incident_report.md.j2`) must produce a report with:
- Title and severity header
- Summary paragraph (technique, tactic, affected host, time range)
- Timeline table (timestamp | action | source | destination | outcome)
- Entities section (attacker IP + geo, victim host, user accounts)
- Evidence excerpts (up to 5 raw log previews, code-block formatted, **sanitized**)
- MITRE technique card (ID, name, tactic, official description excerpt, confidence)
- LLM rationale block
- Recommended actions list

**Critical:** call `sanitize_log_content(raw)` on every raw log line before putting it in the template.

**2. Mermaid attack graph generator (`backend/artifacts/attack_graph.py`)**

```python
def generate_attack_graph(incident: Incident) -> str:
    """Returns a Mermaid graph LR definition string."""
    lines = ["graph LR"]
    for entity in incident.entities:
        safe_label = sanitize_mermaid_label(entity.value)  # strip <>[]{};|
        color = ROLE_COLORS[entity.role]  # red/orange/yellow/blue
        lines.append(f'  {entity.id}["{safe_label}"]')
        lines.append(f'  style {entity.id} fill:{color}')
    for edge in incident.edges:
        lines.append(f'  {edge.from_id} -->|"{sanitize_mermaid_label(edge.label)}"| {edge.to_id}')
    return "\n".join(lines)
```

**3. Containment playbook renderer (`backend/artifacts/playbook_renderer.py`)**

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("backend/artifacts/playbook_templates"),
    autoescape=select_autoescape(["j2"])  # HTML escaping in templates
)

def render_playbook(technique_category: str, ioc_vars: dict) -> str:
    # Validate all IOC variables before rendering
    for key, value in ioc_vars.items():
        validate_ansible_var(key, value)  # raises ValueError on unsafe input
    template = env.get_template(f"{technique_category}.ansible.j2")
    return template.render(**ioc_vars)
```

### Afternoon (13:00–17:30)

**4. Full evaluation suite**

Run your models against the held-out CICIDS2017 attack data (Friday DDoS + PortScan):

```bash
python backend/ml/evaluate.py \
  --test-data data/cicids2017/Friday-WorkingHours-Afternoon-DDos.pcap_IANA_labels.csv \
  --output docs/EVAL_RESULTS.md
```

The evaluation script must compute and write to `EVAL_RESULTS.md`:
- Confusion matrix (TP, FP, TN, FN)
- Precision, Recall, F1, ROC-AUC
- MITRE mapping accuracy on labeled synthetic scenarios (manual spot-check: pick 10 flagged alerts, verify the MITRE technique is at least correct at the tactic level)
- LLM cost: total tokens used, total USD, cost per 1,000 flagged anomalies
- LLM latency: p50, p95 from `llm_call_log`
- Enterprise-volume extrapolation: "At 50M events/day → ~X flagged → ~$Y/day in LLM costs"

**End of Day 4 checklist:**
- [ ] Markdown report generator producing valid, sanitized output for 3 different incident scenarios
- [ ] Mermaid graph generator producing valid graph syntax (render-test in a browser)
- [ ] All 5 Ansible playbook templates written and rendering correctly
- [ ] `EVAL_RESULTS.md` written with real numbers — precision ≥ 0.75, recall ≥ 0.90
- [ ] Cost/latency benchmarks documented and surfaced on the `/ops` page

---

## Day 5 — Hardening, Evaluation, Demo Rehearsal

### All Day

**1. Security self-review (your surfaces)**
- Audit every place a log field or user-controlled string touches a template: `report_generator.py`, `attack_graph.py`, `playbook_renderer.py` — confirm `sanitize_log_content` and `validate_ansible_var` are called before every render
- Audit the LLM prompt: confirm no raw log lines are interpolated into the system prompt or user message
- Run `pip-audit` — fix any critical/high CVEs
- Check `gitleaks` output: confirm no secrets in git history

**2. Load testing (shared with Engineer B)**
- Use the replay producer at 5× then 20× speed
- Monitor Faust consumer lag in Redpanda's admin UI (`rpk topic consume alerts.raw --offset end`)
- Document the bottleneck (expected: LLM call concurrency)
- Record p95 latency at each load level

**3. Chaos testing (your role)**
- Simulate LLM API failure (set invalid API key) — confirm all alerts reach `triage_pending` state
- Verify `llm_call_log` shows the failed attempts with correct error codes
- Restore the API key — confirm the `triage_client.py` handles the valid key correctly on the next call

**4. Demo script preparation**

Your part of the 10-minute demo:

- **T+0:** Start the replay producer with the synthetic brute-force scenario: `python replay_producer.py --scenario brute_force_lateral_movement`
- **T+30s:** Explain what's happening in the pipeline (while Engineer B shows the UI): "Faust is consuming auth.log events, computing sliding-window features — event count, failed-auth ratio, geo-velocity — and calling the Isolation Forest + Autoencoder ensemble"
- **T+60s:** Point to the LLM call: "The ensemble score exceeded the threshold, so we're calling Claude Sonnet with the normalized event summary and the candidate MITRE technique IDs from our heuristic rules"
- **T+90s:** Show the incident appears: "T1110.001 — Brute Force: Password Guessing — with 87% confidence and an analyst-readable rationale"
- **T+3min:** Show the generated Markdown report, attack graph, and containment playbook

**End of Day 5 checklist:**
- [ ] Security self-review complete — no secrets in git, no unsafe template rendering, pip-audit clean
- [ ] Load test results documented in `docs/EVAL_RESULTS.md`
- [ ] Chaos test passed: LLM outage → `triage_pending`; recovery confirmed
- [ ] Demo rehearsed: can narrate the full backend pipeline during the 10-minute walkthrough
- [ ] `EVAL_RESULTS.md` finalized with all metrics
- [ ] `docs/SCALING_PATH.md` written (Flink, K8s, Vault, Batch API — your sections)
