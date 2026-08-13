import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(previous_hash, incident_id, action, actor, timestamp) -> str:
    payload = f"{previous_hash or ''}{incident_id}{action}{actor}{timestamp}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _last_hash(conn, incident_id):
    row = conn.execute(
        "SELECT this_hash FROM ledger WHERE incident_id = ? "
        "ORDER BY id DESC LIMIT 1", (incident_id,)
    ).fetchone()
    return row["this_hash"] if row else None


def _append_ledger(conn, incident_id, action, actor):
    ts = _now()
    prev = _last_hash(conn, incident_id)
    this_hash = _compute_hash(prev, incident_id, action, actor, ts)
    conn.execute(
        "INSERT INTO ledger (incident_id, action, actor, previous_hash, this_hash, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (incident_id, action, actor, prev, this_hash, ts)
    )
    return this_hash


def create_incident(cluster: Dict[str, Any], triage) -> Dict[str, Any]:
    database.init_db()
    t = triage.model_dump() if hasattr(triage, "model_dump") else dict(triage)
    incident_id = str(uuid.uuid4())
    entity = cluster.get("entity", "unknown")
    now = _now()
    sev = t.get("severity")
    sev_val = sev.value if hasattr(sev, "value") else str(sev)
    with database.get_connection() as conn:
        conn.execute(
            """INSERT INTO incidents
               (id, entity, technique, tactic, severity, status,
                confidence, rationale, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)""",
            (incident_id, entity, t.get("technique_id"), t.get("tactic"),
             sev_val, t.get("confidence"), t.get("rationale"), now, now)
        )
        for evt in cluster.get("events", []):
            conn.execute(
                """INSERT INTO alerts
                   (id, incident_id, entity, anomaly_score, status,
                    severity, source_type, created_at)
                   VALUES (?, ?, ?, ?, 'new', ?, ?, ?)""",
                (str(uuid.uuid4()), incident_id, entity,
                 evt.get("anomaly_score", 0.0), sev_val,
                 evt.get("source_type", "unknown"), now)
            )
        _append_ledger(conn, incident_id, "created", "system")
    return get_incident(incident_id)


def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    database.init_db()
    with database.get_connection() as conn:
        row = conn.execute("SELECT * FROM incidents WHERE id = ?",
                           (incident_id,)).fetchone()
        if not row:
            return None
        incident = dict(row)
        alerts = conn.execute(
            "SELECT * FROM alerts WHERE incident_id = ? ORDER BY created_at",
            (incident_id,)).fetchall()
        incident["alerts"] = [dict(a) for a in alerts]
        ledger = conn.execute(
            "SELECT * FROM ledger WHERE incident_id = ? ORDER BY id",
            (incident_id,)).fetchall()
        incident["ledger"] = [dict(e) for e in ledger]
    return incident


def list_incidents(limit=20, status=None, severity=None) -> List[Dict[str, Any]]:
    database.init_db()
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with database.get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM incidents {where} ORDER BY created_at DESC LIMIT ?",
            params).fetchall()
    return [dict(r) for r in rows]


def update_status(incident_id, new_status, actor="analyst"):
    valid = {"open", "investigating", "resolved", "false_positive"}
    if new_status not in valid:
        raise ValueError(f"Invalid status '{new_status}'. Choose from {valid}")
    database.init_db()
    now = _now()
    with database.get_connection() as conn:
        updated = conn.execute(
            "UPDATE incidents SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, incident_id)).rowcount
        if not updated:
            return None
        _append_ledger(conn, incident_id, f"status_changed_to_{new_status}", actor)
    return get_incident(incident_id)


def verify_chain(incident_id: str) -> Dict[str, Any]:
    database.init_db()
    with database.get_connection() as conn:
        entries = conn.execute(
            "SELECT * FROM ledger WHERE incident_id = ? ORDER BY id",
            (incident_id,)).fetchall()
    results, prev_hash, all_valid = [], None, True
    for entry in entries:
        expected = _compute_hash(prev_hash, incident_id, entry["action"],
                                 entry["actor"], entry["timestamp"])
        ok = entry["this_hash"] == expected
        all_valid = all_valid and ok
        results.append({
            "id": entry["id"], "action": entry["action"],
            "timestamp": entry["timestamp"],
            "hash": str(entry["this_hash"])[:16] + "...", "valid": ok,
        })
        prev_hash = entry["this_hash"]
    return {"incident_id": incident_id, "valid": all_valid, "entries": results}
