import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Any

from .normalizers import get_normalizer


def _cicids_normalize_file(filepath: Path, cicids_fn) -> List[Dict[str, Any]]:
    events = []
    with filepath.open("r", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                event = cicids_fn(row)
                if event:
                    events.append(event.model_dump())
            except Exception as exc:
                print(f"  [warn] CICIDS row skipped: {exc}", file=sys.stderr)
    return events


def ingest_file(path: str, source_type: str) -> List[Dict[str, Any]]:
    normalizer_fn = get_normalizer(source_type)
    events = []
    filepath = Path(path)

    if source_type == "cicids":
        return _cicids_normalize_file(filepath, normalizer_fn)

    with filepath.open("r", errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                if source_type == "cloudtrail":
                    raw = json.loads(line)
                    event = normalizer_fn(raw)
                else:
                    event = normalizer_fn(line)
                if event:
                    events.append(event.model_dump())
            except Exception as exc:
                print(f"  [warn] line {line_no} skipped: {exc}", file=sys.stderr)

    return events


def ingest_stdin(source_type: str) -> List[Dict[str, Any]]:
    normalizer_fn = get_normalizer(source_type)
    events = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            event = normalizer_fn(line)
            if event:
                events.append(event.model_dump())
        except Exception:
            pass
    return events

