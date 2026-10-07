"""
StreamGuard - DARPA Dataset Replayer
---------------------------------------
Reads the DARPA edge-stream CSV and publishes it into Kafka at a
controllable rate, simulating live traffic.

Run from the repo root:
    python -m streamguard.ingestion.darpa_replayer data/darpa_processed.csv
    python -m streamguard.ingestion.darpa_replayer data/darpa_processed.csv --rate 500 --limit 5000
"""

import argparse
import csv
import json
import time
from itertools import chain
from pathlib import Path

try:
    from kafka import KafkaProducer
except ImportError as exc:
    raise SystemExit(
        "Install ingestion dependencies: pip install -r streamguard/ingestion/requirements.txt"
    ) from exc

from streamguard.consumer import config


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay DARPA dataset into Kafka")
    parser.add_argument("csv_path", help="path to darpa_processed.csv")
    parser.add_argument("--rate", type=int, default=200, help="events per second to send")
    parser.add_argument("--limit", type=int, default=None, help="max rows to send (default: all)")
    parser.add_argument(
        "--header", choices=("auto", "yes", "no"), default="auto",
        help="CSV header handling (default: auto-detect)",
    )
    parser.add_argument(
        "--preserve-timestamps", action="store_true",
        help="use the CSV timestamp values instead of replay time",
    )
    parser.add_argument(
        "--ground-truth",
        help="optional one-label-per-row CSV; labels are included in Kafka events",
    )
    args = parser.parse_args()
    if args.rate <= 0:
        parser.error("--rate must be greater than zero")

    producer = KafkaProducer(
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    delay = 1.0 / args.rate
    sent = 0
    sim_start = int(time.time())

    with open(args.csv_path, "r", newline="") as f:
        reader = csv.reader(f)
        first = next(reader, None)
        if first is None:
            raise SystemExit("CSV is empty")
        header = args.header == "yes" or (
            args.header == "auto"
            and any(
                value.strip().lower()
                in {"src", "source", "dst", "destination", "timestamp"}
                for value in first
            )
        )
        columns = [x.strip().lower() for x in first] if header else None
        rows = reader if header else chain([first], reader)

        label_file = open(args.ground_truth, "r", newline="") if args.ground_truth else None
        label_reader = None
        if label_file:
            label_reader = csv.reader(label_file)
            label_first = next(label_reader, None)
            if label_first and label_first[0].strip().lower() in {
                "label", "ground_truth", "is_anomaly"
            }:
                pass  # skip header
            else:
                label_reader = chain(([label_first] if label_first else []), label_reader)

        for row in rows:
            if args.limit and sent >= args.limit:
                break

            if columns:
                src_idx = next(
                    (columns.index(k) for k in ("src", "source") if k in columns), 0
                )
                dst_idx = next(
                    (columns.index(k) for k in ("dst", "destination") if k in columns), 1
                )
                ts_idx = columns.index("timestamp") if "timestamp" in columns else 2
            else:
                src_idx, dst_idx, ts_idx = 0, 1, 2

            if len(row) <= max(src_idx, dst_idx, ts_idx):
                raise SystemExit(
                    f"Malformed CSV row {sent + 1}: expected at least 3 columns, got {len(row)}"
                )

            event: dict = {
                "src": str(row[src_idx]),
                "dst": str(row[dst_idx]),
                "timestamp": (
                    int(float(row[ts_idx]))
                    if args.preserve_timestamps
                    else sim_start + (sent // args.rate)
                ),
            }

            if label_reader is not None:
                label_row = next(label_reader, None)
                if label_row is None:
                    raise SystemExit("Ground-truth file has fewer rows than the event CSV")
                event["label"] = int(label_row[-1])

            producer.send(config.KAFKA_TOPIC, value=event)
            sent += 1

            if sent % 500 == 0:
                print(f"[darpa_replayer] sent {sent} events...")

            time.sleep(delay)

    producer.flush()
    if label_file:
        label_file.close()
    print(f"[darpa_replayer] Done. Sent {sent} total events.")


if __name__ == "__main__":
    main()
