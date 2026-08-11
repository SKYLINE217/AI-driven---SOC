"""
SOC Triager — Log Replay Producer
Streams log source files into Redpanda topics at controllable replay speed.

Usage:
    python replay_producer.py --source auth --file data/synthetic_auth_log/brute_force.log --speed 1
    python replay_producer.py --source cicids --file data/cicids2017/Wednesday-workingHours.csv --speed 10
"""

import argparse
import json
import time
import sys
import os
from datetime import datetime, timezone

# Kafka producer (works with Redpanda via Kafka API)
try:
    from kafka import KafkaProducer
except ImportError:
    print("Install kafka-python: pip install kafka-python")
    sys.exit(1)


TOPIC_MAP = {
    'syslog': 'raw.syslog',
    'cloudtrail': 'raw.cloudtrail',
    'auth': 'raw.auth',
    'cicids': 'raw.cicids',
}


def create_producer(bootstrap_servers: str) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8') if isinstance(v, dict) else v.encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3,
    )


def replay_text_file(producer: KafkaProducer, topic: str, filepath: str, speed: float):
    """Replay a text log file line-by-line."""
    print(f"[Replay] Streaming {filepath} → {topic} at {speed}× speed")
    count = 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            producer.send(
                topic,
                value=line,
                key=f"replay-{count}",
            )
            count += 1
            if count % 100 == 0:
                print(f"  [{count}] events sent to {topic}")
            # Throttle based on speed (1× = ~100ms between lines)
            if speed > 0:
                time.sleep(max(0.001, 0.1 / speed))
    producer.flush()
    print(f"[Replay] Done: {count} events sent to {topic}")


def replay_csv_file(producer: KafkaProducer, topic: str, filepath: str, speed: float):
    """Replay a CSV file, sending each row as JSON."""
    import csv
    print(f"[Replay] Streaming CSV {filepath} → {topic} at {speed}× speed")
    count = 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Clean column names (CICIDS2017 has leading spaces)
            cleaned = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
            producer.send(
                topic,
                value=json.dumps(cleaned).encode('utf-8'),
                key=f"csv-{count}",
            )
            count += 1
            if count % 500 == 0:
                print(f"  [{count}] rows sent to {topic}")
            if speed > 0:
                time.sleep(max(0.0001, 0.01 / speed))
    producer.flush()
    print(f"[Replay] Done: {count} rows sent to {topic}")


def replay_json_file(producer: KafkaProducer, topic: str, filepath: str, speed: float):
    """Replay a JSON-lines file or JSON array."""
    print(f"[Replay] Streaming JSON {filepath} → {topic} at {speed}× speed")
    count = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        # Try JSON array
        if content.startswith('['):
            events = json.loads(content)
            for event in events:
                producer.send(topic, value=json.dumps(event).encode('utf-8'), key=f"json-{count}")
                count += 1
                if speed > 0:
                    time.sleep(max(0.001, 0.1 / speed))
        else:
            # JSON lines
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                producer.send(topic, value=line.encode('utf-8'), key=f"jsonl-{count}")
                count += 1
                if speed > 0:
                    time.sleep(max(0.001, 0.1 / speed))
    producer.flush()
    print(f"[Replay] Done: {count} events sent to {topic}")


def main():
    parser = argparse.ArgumentParser(description='SOC Triager Log Replay Producer')
    parser.add_argument('--source', required=True, choices=TOPIC_MAP.keys(),
                        help='Log source type')
    parser.add_argument('--file', required=True, help='Path to source file')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Replay speed multiplier (0 = max speed)')
    parser.add_argument('--broker', default='localhost:19092',
                        help='Kafka bootstrap servers')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        sys.exit(1)

    topic = TOPIC_MAP[args.source]
    producer = create_producer(args.broker)

    ext = os.path.splitext(args.file)[1].lower()
    if ext == '.csv':
        replay_csv_file(producer, topic, args.file, args.speed)
    elif ext in ('.json', '.jsonl'):
        replay_json_file(producer, topic, args.file, args.speed)
    else:
        replay_text_file(producer, topic, args.file, args.speed)

    producer.close()


if __name__ == '__main__':
    main()
