"""
CIC-IDS2017 Replayer

Streams pre-processed CIC-IDS2017 parquet data into Kafka.

Usage:
    python -m streamguard.ingestion.cicids2017_replayer \\
        data/processed/cic-ids2017.parquet --rate 100 --sample 10000
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer

from streamguard.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay CIC-IDS2017 into Kafka")
    parser.add_argument("parquet_path", help="Path to processed CIC-IDS2017 parquet file")
    parser.add_argument("--rate", type=int, default=100, help="Events per second")
    parser.add_argument("--sample", type=int, default=None, help="Max events to send")
    parser.add_argument("--preserve-timestamps", action="store_true", help="Use original timestamps")
    args = parser.parse_args()

    print(f"Loading {args.parquet_path}...")
    df = pd.read_csv(args.parquet_path) if args.parquet_path.endswith('.csv') else pd.read_parquet(args.parquet_path)

    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42)

    print(f"Loaded {len(df)} flows")

    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    delay = 1.0 / args.rate
    sent = 0
    sim_start = int(time.time())

    print(f"Replaying at {args.rate} events/sec...")

    for idx, row in df.iterrows():
        event = {
            "src": str(row.get("Source IP", "0.0.0.0")),
            "dst": str(row.get("Destination IP", "0.0.0.0")),
            "timestamp": (
                int(pd.Timestamp(row["Timestamp"]).timestamp())
                if args.preserve_timestamps and "Timestamp" in row
                else sim_start + (sent // args.rate)
            ),
            "label": int(row.get("is_attack", 0)) if "is_attack" in row else None,
            "attack_type": str(row.get("attack_type", "Benign")) if "attack_type" in row else None,
        }

        # Add key features for analysis
        for col in df.columns:
            if col not in ["Source IP", "Destination IP", "Timestamp", "Label", "is_attack", "attack_type", "Flow ID"]:
                try:
                    event[col] = float(row[col])
                except (ValueError, TypeError):
                    pass

        producer.send(settings.kafka_topic, value=event)
        sent += 1

        if sent % 1000 == 0:
            print(f"  Sent {sent} flows...")

        time.sleep(delay)

    producer.flush()
    print(f"Done. Sent {sent} flows.")


if __name__ == "__main__":
    main()
