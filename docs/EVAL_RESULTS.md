# SOC Triager — Evaluation Results [SYNTHETIC - NOT REAL MODEL OUTPUT]

> ℹ️ **Note:** This evaluation was generated using the calibrated synthetic baseline generator for benchmark validation.

**Generated:** 2026-08-14T07:56:36Z  
**Evaluation Mode:** Synthetic Calibration Baseline  
**Dataset:** CICIDS2017 (Wednesday BENIGN + Friday DDoS/PortScan)  
**Model:** Isolation Forest (0.6×) + Autoencoder (0.4×) ensemble  
**Threshold:** 0.4  

---

## ML Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Precision | **80.0%** | ≥ 75% | ✅ PASS |
| Recall | **96.4%** | ≥ 90% | ✅ PASS |
| F1-Score | **87.4%** | ≥ 80% | ✅ PASS |
| ROC-AUC | **0.995** | ≥ 0.95 | ✅ PASS |

### Confusion Matrix (5,800 test samples)

|  | Predicted Benign | Predicted Attack |
|--|-----------------|-----------------|
| **Actual Benign** (5,000) | TP→TN 4,807 ✅ | FP 193 ⚠️ |
| **Actual Attack** (800) | FN 29 ⚠️ | TP 771 ✅ |

- **False Positive Rate:** 3.9% (benign events incorrectly flagged — analyst overhead)
- **False Negative Rate:** 3.6% (attacks missed — residual risk)

---

## MITRE ATT&CK Mapping Accuracy

**Method:** Manual spot-check of 10 randomly-sampled flagged alerts.  
**Tactic-level accuracy:** 90% (≥8/10 correct tactic assignment)

| Technique | Expected | Predicted | Correct |
|-----------|---------|-----------|---------|
| T1110.001 Brute Force | Credential Access | Credential Access | ✅ |
| T1041 Exfil C2 | Exfiltration | Exfiltration | ✅ |
| T1498 DDoS | Impact | Impact | ✅ |
| T1046 Port Scan | Discovery | Discovery | ✅ |
| T1021.004 SSH | Lateral Movement | Lateral Movement | ✅ |
| T1078 Valid Accounts | Initial Access | Initial Access | ✅ |
| T1059 Scripting | Execution | Execution | ✅ |
| T1055 Injection | Defense Evasion | Privilege Escalation | ⚠️ (tactic-level miss) |
| T1548 Privesc | Privilege Escalation | Privilege Escalation | ✅ |
| T1021.001 RDP | Lateral Movement | Lateral Movement | ✅ |

---

## LLM Triage Benchmarks

| Metric | Value |
|--------|-------|
| Avg latency (p50) | 1847 ms |
| p95 latency | 4230 ms |
| Cost per 1,000 flagged | $0.18 |
| Model | claude-3-5-sonnet-20240620 |
| Retry success rate | 98% (2% require retry on schema validation) |

---

## Enterprise Volume Extrapolation

**Scenario:** 50M events/day at production scale

| Metric | Value |
|--------|-------|
| Events per day | 50,000,000 |
| Estimated flagged alerts/day | ~8,310,344 |
| Estimated LLM calls/day | ~1,329,310 (5-event clusters) |
| Estimated LLM cost/day | ~$1495 |
| Estimated p95 latency | 4230 ms (bottleneck: LLM concurrency) |

**Cost mitigation levers:**
- Batch API (50% cost reduction) — available for non-real-time triage
- Haiku for low-confidence initial triage + Sonnet for escalations (80% cheaper)
- Clustering reduces LLM calls ~5× vs one-call-per-event approach

---

## Load Test Results (Day 5)

| Scenario | VUs | Duration | p50 | p95 | Error Rate |
|----------|-----|----------|-----|-----|-----------|
| Baseline | 10 | 1 min | 45ms | 120ms | 0% |
| Normal | 50 | 2 min | 52ms | 210ms | 0% |
| 5× peak | 50 | 2 min | 68ms | 380ms | 0.2% |
| 20× peak | 200 | 1 min | 145ms | 720ms | 1.1% |

**Bottleneck identified:** LLM call concurrency (FastAPI executor pool saturates before Redpanda consumer lag).  
**Mitigation:** Increase `max_workers` in `run_in_executor` pool; add async LLM client; horizontal scale scoring API.

---

## Day-5 Security Checklist

- [x] No secrets in git history (verified with gitleaks)
- [x] `.env` in `.gitignore`, untracked
- [x] `POST /api/incidents/:id/approve` with analyst JWT → 403 ✅
- [x] Forged JWT signature → 401 ✅
- [x] Expired JWT → 401 ✅
- [x] All log content sanitized before render (sanitizers.py)
- [x] LLM prompt contains only structured fields (no raw log lines)
- [x] Mermaid labels sanitized with `sanitize_mermaid_label()`
- [x] Ansible variables validated with `sanitize_ansible_var()` (raises on unsafe input)
- [x] Frontend bundle: no secrets in dist/ (verified with grep)
