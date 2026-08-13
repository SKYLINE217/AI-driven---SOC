#!/usr/bin/env python3
"""
SOC Triager - Pure Python CLI
Usage: python soc_triager.py <command> [options]
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import database


def _build_event_context(cluster: dict) -> dict:
    top_feats = {f["name"]: f.get("value", 0.0) for f in cluster.get("top_features", [])}
    rep = cluster["events"][0] if cluster.get("events") else {}
    src = rep.get("source", {})
    dst = rep.get("destination", {})
    evt = rep.get("event", {})
    net = rep.get("network", {})
    user = rep.get("user", {})

    def _is_internal(ip: str) -> bool:
        if not ip:
            return False
        return ip.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2",
                               "172.30.", "172.31.", "192.168.", "127."))

    ctx = {
        "event_type": evt.get("category", ""),
        "action": evt.get("action", ""),
        "dest_port": dst.get("port", 0) or 0,
        "event_count_1m": top_feats.get("event_count_1m", 0),
        "event_count_5m": top_feats.get("event_count_5m", 0),
        "distinct_dest_ports": top_feats.get("distinct_dest_ports", 0),
        "dest_ip_fanout": top_feats.get("dest_ip_fanout", 0),
        "bytes_transferred": top_feats.get("bytes_transferred", 0),
        "geo_velocity_kmh": top_feats.get("geo_velocity_kmh", 0),
        "source_is_internal": _is_internal(src.get("ip", "")),
        "dest_is_internal": _is_internal(dst.get("ip", "")),
        "dest_is_external": (dst.get("ip", "") and not _is_internal(dst.get("ip", ""))),
        "anomaly_score": cluster.get("max_score", 0.0),
        "command_line": rep.get("process", {}).get("command_line", ""),
        "user": user.get("name", ""),
        "api_call": evt.get("action", ""),
        "parent_process": rep.get("process", {}).get("parent", ""),
        "process": rep.get("process", {}).get("name", ""),
    }
    return ctx


def _map_techniques_adapter(cluster: dict) -> dict:
    try:
        from mitre.mapping_engine import MitreRuleEngine, get_technique
        ctx = _build_event_context(cluster)
        engine = MitreRuleEngine()
        candidates = engine.get_candidate_techniques(ctx)
    except Exception as exc:
        print(f"  [warn] MITRE rule engine unavailable: {exc}", file=sys.stderr)
        candidates = []

    if not candidates:
        return {
            "technique_ids": ["T0000"],
            "technique_name": "Unknown Technique",
            "tactic": "Unknown",
        }

    primary = candidates[0]
    try:
        from mitre.mapping_engine import get_technique
        meta = get_technique(primary)
        return {
            "technique_ids": candidates,
            "technique_name": meta.get("name", "Unknown"),
            "tactic": meta.get("tactic", "Unknown"),
        }
    except Exception as exc:
        print(f"  [warn] MITRE STIX lookup failed: {exc}", file=sys.stderr)
        return {
            "technique_ids": candidates,
            "technique_name": primary,
            "tactic": "Unknown",
        }


def _generate_artifacts(incident: dict, output_dir: str):
    from artifacts.report_generator import generate_incident_report
    from artifacts.attack_graph import generate_attack_graph
    from artifacts.playbook_renderer import render_playbook

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    title = f"{incident.get('entity', 'Unknown')} - {incident.get('technique', 'T0000')}"
    llm_rationale = incident.get("rationale", "")
    recommended_action = (
        incident.get("recommended_immediate_action")
        if isinstance(incident, dict) and "recommended_immediate_action" in incident
        else "Isolate host pending investigation."
    )
    technique_id = incident.get("technique", "T0000")
    technique_name = technique_id
    alerts_ids = [a["id"] for a in incident.get("alerts", [])]
    entities = []
    if incident.get("entity"):
        entities.append({
            "role": "attacker",
            "ip": incident["entity"],
            "host": "",
            "user": "",
            "geo_country": "",
        })
    for a in incident.get("alerts", [])[:3]:
        pass

    rich_incident = dict(incident)
    rich_incident.setdefault("title", title)
    rich_incident.setdefault("llm_rationale", llm_rationale)
    rich_incident.setdefault("recommended_action", recommended_action)
    rich_incident.setdefault("technique_id", technique_id)
    rich_incident.setdefault("technique_name", technique_name)
    rich_incident["alerts"] = alerts_ids
    rich_incident["entities"] = entities
    if "mitre_description" not in rich_incident:
        try:
            from mitre.mapping_engine import get_technique
            meta = get_technique(technique_id)
            rich_incident["mitre_description"] = meta.get("description", "")
        except Exception:
            rich_incident["mitre_description"] = ""

    report_path = out / f"{incident['id']}_report.md"
    graph_path = out / f"{incident['id']}_graph.mmd"
    playbook_path = out / f"{incident['id']}_playbook.yml"

    try:
        report_path.write_text(generate_incident_report(rich_incident), encoding="utf-8")
    except Exception as exc:
        print(f"  [warn] Report generation failed: {exc}", file=sys.stderr)
    try:
        graph_path.write_text(generate_attack_graph(rich_incident), encoding="utf-8")
    except Exception as exc:
        print(f"  [warn] Graph generation failed: {exc}", file=sys.stderr)
    try:
        playbook_path.write_text(render_playbook(rich_incident), encoding="utf-8")
    except Exception as exc:
        print(f"  [warn] Playbook generation failed: {exc}", file=sys.stderr)

    print(f"    -> Artifacts written to {out}/")


def cmd_ingest(args):
    from ingestion.file_ingestor import ingest_file
    from ml.scorer import score_events
    from mitre.alert_clustering import cluster_alerts
    from services.incident_service import create_incident
    from services.triage import deterministic_triage
    from display import print_incident_summary

    events = ingest_file(args.file, source_type=args.source)
    if not events:
        print(f"No events loaded from {args.file}")
        return

    try:
        scored = score_events(events)
    except FileNotFoundError as exc:
        print(f"Error: {exc}. Run 'python soc_triager.py train' first.")
        sys.exit(2)

    anomalies = [s for s in scored if s.get("anomaly_score", 0.0) > args.threshold]
    print(f"\n[+] {len(events)} events ingested, {len(anomalies)} anomalies detected (threshold={args.threshold})")

    if not anomalies:
        print("No anomalies raised above threshold.")
        return

    clusters = cluster_alerts(anomalies)
    print(f"[+] {len(clusters)} alert cluster(s) formed\n")

    for cluster in clusters:
        techniques = _map_techniques_adapter(cluster)
        triage = deterministic_triage(
            events=cluster["events"],
            anomaly_score=cluster["max_score"],
            top_features=cluster["top_features"],
            candidate_technique_ids=techniques["technique_ids"],
            technique_name=techniques["technique_name"],
            tactic=techniques["tactic"],
        )
        incident = create_incident(cluster, triage)
        if hasattr(triage, "recommended_immediate_action"):
            incident["recommended_immediate_action"] = triage.recommended_immediate_action
        print_incident_summary(incident)

        if args.artifacts:
            _generate_artifacts(incident, args.output_dir)


def cmd_train(args):
    from ml.train import train_models
    train_models(data_dir=args.data_dir, output_dir=args.model_dir)


def cmd_evaluate(args):
    from ml.evaluate import generate_synthetic_evaluation, compute_llm_metrics, generate_report
    metrics = generate_synthetic_evaluation()
    llm = compute_llm_metrics()

    print("SOC Triager - Evaluation")
    print("=" * 60)
    print(f"Precision:  {metrics['precision']:.1%}")
    print(f"Recall:     {metrics['recall']:.1%}")
    print(f"F1-Score:   {metrics['f1']:.1%}")
    print(f"ROC-AUC:    {metrics['roc_auc']:.3f}")
    print(f"\nTP: {metrics['true_positives']}  TN: {metrics['true_negatives']}  "
          f"FP: {metrics['false_positives']}  FN: {metrics['false_negatives']}")

    report = generate_report(metrics, llm, args.output)
    print(f"\nReport written to: {args.output}")

    passed = metrics["precision"] >= 0.75 and metrics["recall"] >= 0.90
    if not passed:
        print("FAIL: Targets not met - review model threshold")
        sys.exit(1)
    print("PASS: All ML targets met (precision >= 75%, recall >= 90%)")


def cmd_generate(args):
    from pathlib import Path
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start = datetime.utcnow()
    count_written = 0

    if args.type == "auth":
        from ingestion.generators.auth_log_generator import (
            generate_normal_traffic,
            generate_brute_force_attack,
            generate_privilege_escalation,
            generate_lateral_movement,
            generate_full_scenario,
        )
        if args.count >= 2000:
            gen = generate_full_scenario(start_time=start)
        else:
            gen = generate_normal_traffic(
                start_time=start,
                duration_minutes=max(args.count // 2, 5),
                events_per_minute=max(args.count / max(args.count // 60, 5), 1.0),
                hostname="prod-db-03",
            )
        with output_path.open("w", encoding="utf-8") as f:
            for line in gen:
                print(line, file=f)
                count_written += 1
                if count_written >= args.count:
                    break
            if count_written < args.count:
                extra = args.count - count_written
                for line in generate_normal_traffic(
                    start_time=start + timedelta(hours=1),
                    duration_minutes=max(extra // 2, 5),
                    events_per_minute=max(extra / 10.0, 1.0),
                    hostname="prod-db-03",
                ):
                    print(line, file=f)
                    count_written += 1
                    if count_written >= args.count:
                        break

    elif args.type == "cloudtrail":
        from ingestion.generators.cloudtrail_generator import (
            generate_normal_cloudtrail,
            generate_full_scenario,
        )
        import json
        gen = generate_full_scenario(start_time=start)
        with output_path.open("w", encoding="utf-8") as f:
            for evt in gen:
                if isinstance(evt, dict):
                    line = json.dumps(evt)
                else:
                    line = str(evt)
                print(line, file=f)
                count_written += 1
                if count_written >= args.count:
                    break
            if count_written < args.count:
                extra = args.count - count_written
                for evt in generate_normal_cloudtrail(
                    start_time=start + timedelta(hours=1),
                    duration_minutes=max(extra // 2, 5),
                    events_per_minute=max(extra / 10.0, 1.0),
                ):
                    if isinstance(evt, dict):
                        line = json.dumps(evt)
                    else:
                        line = str(evt)
                    print(line, file=f)
                    count_written += 1
                    if count_written >= args.count:
                        break

    print(f"[+] {count_written} {args.type} log lines written to {output_path}")


def cmd_list_incidents(args):
    from services.incident_service import list_incidents
    from display import print_incident_table
    incidents = list_incidents(limit=args.limit)
    if not incidents:
        print("No incidents recorded yet.")
        return
    print_incident_table(incidents)


def cmd_show_incident(args):
    from services.incident_service import get_incident, verify_chain
    from display import print_incident_detail

    incident = get_incident(args.id)
    if not incident:
        print(f"Incident {args.id} not found.")
        sys.exit(1)
    print_incident_detail(incident)

    chain = verify_chain(args.id)
    status = "\n[bold green]VALID[/bold green]" if chain["valid"] else "\n[bold red]INVALID[/bold red]"
    try:
        from display import console
        console.print(f"\nHash chain integrity check: {status}")
        for entry in chain["entries"]:
            mark = "OK" if entry["valid"] else "FAIL"
            console.print(f"  [{str(entry['timestamp'])[:19]}] {entry['action']} "
                          f"({entry['hash']}) {mark}")
    except Exception:
        print(f"\nHash chain valid: {chain['valid']}")
        for entry in chain["entries"]:
            mark = "OK" if entry["valid"] else "FAIL"
            print(f"  [{str(entry['timestamp'])[:19]}] {entry['action']} "
                  f"({entry['hash']}) {mark}")


def cmd_update_status(args):
    from services.incident_service import update_status, get_incident
    from display import print_incident_detail

    inc = get_incident(args.id)
    if not inc:
        print(f"Incident {args.id} not found.")
        sys.exit(1)

    updated = update_status(args.id, args.status, actor=args.actor)
    if updated is None:
        print(f"Failed to update incident {args.id}")
        sys.exit(1)
    print(f"[+] Status set to '{args.status}' by {args.actor}")
    print_incident_detail(updated)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="soc_triager",
        description="SOC Triager - Pure Python security operations automation",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest and analyze a log file")
    p_ingest.add_argument("file", help="Path to log file")
    p_ingest.add_argument("--source", choices=["syslog", "cloudtrail", "auth", "auth_log", "cicids"],
                          required=True, help="Log source type")
    p_ingest.add_argument("--threshold", type=float, default=0.40,
                          help="Anomaly score threshold (default 0.40)")
    p_ingest.add_argument("--artifacts", action="store_true",
                          help="Generate Markdown report, Mermaid graph, and Ansible playbook")
    p_ingest.add_argument("--output-dir", default="./output",
                          help="Directory for artifact output (default ./output)")
    p_ingest.set_defaults(func=cmd_ingest)

    p_train = sub.add_parser("train", help="Train ML models on CICIDS2017 data")
    p_train.add_argument("--data-dir", default="./data/cicids2017")
    p_train.add_argument("--model-dir", default="./data/models")
    p_train.set_defaults(func=cmd_train)

    p_eval = sub.add_parser("evaluate", help="Evaluate trained models")
    p_eval.add_argument("--data-dir", default="./data/cicids2017")
    p_eval.add_argument("--model-dir", default="./data/models")
    p_eval.add_argument("--output", default="docs/EVAL_RESULTS.md")
    p_eval.set_defaults(func=cmd_evaluate)

    p_gen = sub.add_parser("generate", help="Generate synthetic log data")
    p_gen.add_argument("--type", choices=["auth", "cloudtrail"], required=True)
    p_gen.add_argument("--output", default="./data/synthetic/output.log")
    p_gen.add_argument("--count", type=int, default=1000)
    p_gen.set_defaults(func=cmd_generate)

    p_list = sub.add_parser("incidents", help="List all recorded incidents")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list_incidents)

    p_show = sub.add_parser("show", help="Show a specific incident")
    p_show.add_argument("id", help="Incident ID")
    p_show.set_defaults(func=cmd_show_incident)

    p_upd = sub.add_parser("update", help="Update incident status")
    p_upd.add_argument("id", help="Incident ID")
    p_upd.add_argument("--status", required=True,
                       choices=["open", "investigating", "resolved", "false_positive"])
    p_upd.add_argument("--actor", default="analyst", help="Analyst name for ledger")
    p_upd.set_defaults(func=cmd_update_status)

    return parser


if __name__ == "__main__":
    database.init_db()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
