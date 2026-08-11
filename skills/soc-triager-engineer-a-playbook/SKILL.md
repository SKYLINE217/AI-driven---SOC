---
name: soc-triager-engineer-a-playbook
description: Use this skill whenever the user is acting as, or asking on behalf of, SOC Triager's "Engineer A — ML/Data/Backend Lead" and wants to know what to do today, in what order, or with what code/commands — data ingestion, normalizers, feature engineering, Isolation Forest/Autoencoder training, MLflow, MITRE mapping rules, the LLM triage client, artifact generators, evaluation, or the Day 5 security/chaos/demo checklist for their surfaces. Trigger this for "what should I do next", "give me today's checklist", "write the normalizer/feature/training/triage code", or any Day 1–5 task explicitly assigned to Engineer A. This is a personal, sequential, checklist-driven playbook — follow it in order rather than jumping ahead, and check off items against the end-of-day checklists before moving to the next day.
---

# SOC Triager — Engineer A Playbook (ML / Data / Backend Lead)

> **Your role:** you own the intelligence core — everything that turns raw logs into meaningful, prioritized, MITRE-mapped incidents. Engineer B owns the platform that surfaces your outputs (see the companion `soc-triager-engineer-b-playbook` skill for their side).
> **Daily rhythm:** 09:00 standup (15 min) · 13:00 integration checkpoint (20 min) · 17:30 end-of-day deploy verification (15 min).
> **Golden rule:** never write code without a test. Never push a model that isn't registered in MLflow. Never let a log field or user-controlled string reach a template unvalidated.

## Day 1 — Architecture lock, data ingestion, synthetic data

**Morning:**
1. Attend the architecture kickoff (09:00–10:30, shared). Lock the ECS event schema (this is your contract with Engineer B — don't change field names later without a sync). Agree on the monorepo layout `/backend /frontend /infra /data /docs`. Confirm your Anthropic API key works: write `hello_claude.py` calling `claude-sonnet-4-6` with a trivial prompt; fix it before writing anything else.
2. `cd soc-triager/backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt --require-hashes && cp .env.example .env` (fill in secrets).
3. Download CICIDS2017 (Wednesday working-hours + Friday DDoS/PortScan subsets) into `/data/cicids2017/`, and the Elastic sample security logs into `/data/elastic_samples/`. Inspect columns; document every column you plan to use in `backend/ml/FEATURE_COLUMNS.md`.
4. Write source normalizers in `backend/ingestion/normalizers/`, one per source type (syslog RFC5424, CloudTrail JSON, auth.log, CICIDS CSV), each returning a `NormalizedEvent`. Write ≥3 unit tests per normalizer in `backend/tests/test_normalizers.py`: happy path, missing fields (must not raise — use defaults), injected special characters (must not raise).
5. Write synthetic data generators (`backend/ingestion/generators/`): `cloudtrail_generator.py`, `auth_log_generator.py`. Deterministic demo scenario: 20 `Failed password` lines from the same source IP within 90 seconds, targeting 4 distinct usernames.
6. Stand up MLflow (`docker compose up -d mlflow`, UI at `localhost:5000`); verify with a trivial logged run.

**Afternoon:**
7. 13:00 integration checkpoint — confirm ECS schema agreed, Engineer B's Redpanda topics exist (`raw.syslog`, `raw.cloudtrail`, `raw.auth`, `raw.cicids`), and Pydantic models for `NormalizedEvent`/`FeatureVector`/`ScoreResponse` are agreed.
8. Wire the Faust normalizer agent: make your normalizers importable via `backend/ingestion/normalizers/__init__.py::get_normalizer(source_type)`.

**End of Day 1 checklist:** all 4 normalizers written+tested · synthetic generators produce valid output · MLflow running · trivial Claude call works · ECS schema agreed · normalizer interface importable by the Faust worker (confirm with Engineer B).

## Day 2 — Feature engineering, ML training, evaluation harness

**Morning:**
1. Implement `compute_windowed_features(entity_key, redis_client)` in `backend/ml/feature_engineering.py` returning a `FeatureVector` with: `event_count_1m/5m/1h`, `failed_auth_ratio`, `distinct_dest_ports`, `dest_ip_fanout`, `bytes_transferred`, `tod_zscore`, `geo_velocity_kmh` (defaults to 0 for new entities with no history — see `soc-triager-backend` for the exact Redis key patterns per feature).
2. Prepare the CICIDS2017 split — Wednesday BENIGN rows for training the normal baseline, Friday DDoS/PortScan for held-out evaluation. Document the CICIDS→FeatureVector column mapping in `FEATURE_COLUMNS.md`.
3. Train Isolation Forest (`n_estimators=200, contamination='auto', random_state=42`) in an MLflow run; log params/metrics; target **precision ≥ 0.75, recall ≥ 0.90**.

**Afternoon:**
4. Train the Autoencoder (`backend/ml/autoencoder.py`) — 3-layer symmetric bottleneck (`input→32→16→8→16→32→input`), PyTorch, trained on benign-only data. Anomaly score = MSE reconstruction error, converted to a percentile against the benign distribution.
5. Build the ensemble (`0.6×IF + 0.4×AE`); produce a precision-recall curve; pick and document the threshold in `backend/ml/THRESHOLD_DECISION.md`.
6. Register both models in MLflow and transition to "production" stage.

**End of Day 2 checklist:** `FeatureVector` implemented with all 9+ features · Isolation Forest trained, precision ≥0.75/recall ≥0.90 · Autoencoder trained, reconstruction-error distribution logged · threshold documented · both models at "production" stage in MLflow · confirm Engineer B's Scoring API loads them correctly.

## Day 3 — MITRE mapping + LLM triage client

**Morning:**
1. Set up the MITRE corpus loader (`backend/mitre/mapping_engine.py`) using `mitreattack.stix20.MitreAttackData` against the pinned `enterprise-attack-v15.1.json`.
2. Write ≥15 heuristic candidate rules in `backend/mitre/rules.yaml` covering: brute force (SSH/RDP/HTTP) → T1110.x, port scan → T1046, DDoS → T1498, lateral movement (SMB/RDP) → T1021.x, privilege escalation → T1548.x, data exfiltration → T1041, impossible travel (geo-velocity) → T1078, process injection → T1055, suspicious process lineage → T1059. Test with `pytest backend/tests/test_mitre_mapping.py` using synthetic event fixtures.

**Afternoon:**
3. Build the LLM triage client (`backend/llm/triage_client.py`) using the Anthropic SDK + a Pydantic `TriageResult` schema (`technique_id`, `technique_name`, `tactic`, `confidence` 0-1, `rationale` ≤500 chars, `severity` literal, `recommended_immediate_action` ≤300 chars). Retry up to 3 attempts; reject any `technique_id` not in the candidate list. See `soc-triager-backend` for the full system prompt and code. Write unit tests with mocked responses (`unittest.mock.patch` — never hit the real API in unit tests) plus one integration test with a real, small, deterministic fixture call.

**End of Day 3 checklist:** MITRE mapping engine integrated with pinned corpus · 15+ heuristic rules tested · LLM triage client with retry/schema-validation/logging · mocked unit tests passing · real-call integration test passing · confirm with Engineer B that incident-correlation clustering is compatible with your `TriageResult` schema.

## Day 4 — Artifact generation + evaluation report

**Morning:**
1. Markdown incident report generator (`backend/artifacts/report_generator.py`, Jinja2 template `templates/incident_report.md.j2`): title/severity header, summary paragraph, timeline table, entities section, evidence excerpts (≤5 raw lines, code-block, **sanitized**), MITRE technique card, LLM rationale, recommended actions. **Critical: call `sanitize_log_content(raw)` on every raw log line before templating — see `soc-triager-security` for the exact sanitizer.**
2. Mermaid attack graph generator (`backend/artifacts/attack_graph.py`) — builds `graph LR`, sanitizes labels (`sanitize_mermaid_label` strips `<>[]{};|`), colors nodes by role.
3. Containment playbook renderer (`backend/artifacts/playbook_renderer.py`) — Jinja2 with `autoescape=select_autoescape(["j2"])`; validate every IOC variable with `validate_ansible_var` before rendering (raises `ValueError` on unsafe input).

**Afternoon:**
4. Run the full evaluation suite against held-out CICIDS2017 attack data (`python backend/ml/evaluate.py --test-data data/cicids2017/Friday-WorkingHours-Afternoon-DDos.pcap_IANA_labels.csv --output docs/EVAL_RESULTS.md`). Must compute and write: confusion matrix, precision/recall/F1/ROC-AUC, MITRE mapping accuracy (manual spot-check of 10 flagged alerts, tactic-level correctness), LLM cost (total tokens/USD, cost per 1,000 flagged), LLM latency (p50/p95 from `llm_call_log`), and an enterprise-volume extrapolation ("At 50M events/day → ~X flagged → ~$Y/day").

**End of Day 4 checklist:** report generator producing valid, sanitized output for 3 scenarios · Mermaid graphs render-tested in a browser · all 5 Ansible playbook templates render correctly · `EVAL_RESULTS.md` has real numbers (precision ≥0.75, recall ≥0.90) · cost/latency benchmarks surfaced on `/ops`.

## Day 5 — Hardening, evaluation, demo rehearsal

**All day:**
1. **Security self-review (your surfaces):** audit every place a log field/user string touches a template (`report_generator.py`, `attack_graph.py`, `playbook_renderer.py`) — confirm sanitizers are called before every render; confirm no raw log lines are interpolated into the LLM prompt; run `pip-audit` and fix critical/high CVEs; check `gitleaks` output for secrets in git history.
2. **Load testing** (shared with Engineer B): replay at 5× then 20× speed; monitor Faust consumer lag (`rpk topic consume alerts.raw --offset end`); document the bottleneck (expect LLM call concurrency) and its mitigation; record p95 latency at each level.
3. **Chaos testing (your role):** set an invalid `ANTHROPIC_API_KEY` — confirm all alerts reach `triage_pending`, and `llm_call_log` shows failed attempts with correct error codes; restore the key and confirm the client recovers on the next call.
4. **Demo script (your part of the 10-minute walkthrough):** T+0 start the replay producer with the brute-force/lateral-movement scenario; T+30s narrate the pipeline (Faust → features → IF+AE ensemble); T+60s explain the LLM call (Claude Sonnet + candidate MITRE IDs); T+90s show the incident appearing (T1110.001, 87% confidence, rationale); T+3min show the generated report, attack graph, and playbook.

**End of Day 5 checklist:** security self-review complete (no secrets in git, no unsafe rendering, pip-audit clean) · load test results in `EVAL_RESULTS.md` · chaos test passed (LLM outage → `triage_pending`, recovery confirmed) · demo rehearsed · `EVAL_RESULTS.md` finalized · your sections of `docs/SCALING_PATH.md` (Flink, K8s, Vault, Batch API) written.

## Related skills

For the shared architecture/schema/API contract, consult `soc-triager-system-architecture`, `soc-triager-backend`, and `soc-triager-api-reference`. For security details behind the "sanitize before render" and "never send raw logs to the LLM" rules, consult `soc-triager-security`. For the overall sprint context and non-goals, consult `soc-triager-plan`.
