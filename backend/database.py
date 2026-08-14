import sqlite3
from pathlib import Path
from .config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS incidents (
            id          TEXT PRIMARY KEY,
            entity      TEXT NOT NULL,
            technique   TEXT,
            tactic      TEXT,
            severity    TEXT,
            status      TEXT DEFAULT 'open',
            confidence  REAL,
            rationale   TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id           TEXT PRIMARY KEY,
            incident_id  TEXT REFERENCES incidents(id),
            entity       TEXT,
            anomaly_score REAL,
            status       TEXT DEFAULT 'new',
            severity     TEXT,
            source_type  TEXT,
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ledger (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id  TEXT REFERENCES incidents(id),
            action       TEXT NOT NULL,
            actor        TEXT,
            previous_hash TEXT,
            this_hash    TEXT NOT NULL,
            timestamp    TEXT NOT NULL
        );
        """)

