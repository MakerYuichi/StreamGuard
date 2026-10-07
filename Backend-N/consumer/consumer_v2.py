"""
StreamGuard - Phase 2 Consumer
Real scoring (MIDAS) + DB writes + WebSocket broadcast, all wired together.
"""

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kafka import KafkaConsumer

import config
import db_writer
import websocket_server
from algorithm.midas_scorer import MidasScorer


def main():
    print("[consumer_v2] Starting WebSocket server...")
    websocket_server.start_in_background()

    time.sleep(0.25)

    print(
        f"[consumer_v2] Connecting to Kafka at "
        f"{config.KAFKA_BOOTSTRAP_SERVERS} ..."
    )

    consumer = KafkaConsumer(
        config.KAFKA_TOPIC,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="streamguard-consumer-group-v2",
    )

    scorer = MidasScorer(
        tick_length_seconds=10,
        anomaly_threshold=config.ANOMALY_THRESHOLD
    )

    print(
        f"[consumer_v2] Listening on '{config.KAFKA_TOPIC}' "
        f"with REAL MIDAS scoring...\n"
    )

    event_count = 0
    alert_count = 0

    start_time = time.time()

    try:
        for message in consumer:

            raw = message.value

            scored = scorer.score_edge(
                raw["src"],
                raw["dst"],
                raw["timestamp"]
            )

            if raw.get("label") is not None:
                scored["label"] = int(raw["label"])

            event_count += 1

            # Write every scored event to the database
            db_writer.write_score(scored)

            # Handle anomaly alerts
            if scored["is_alert"]:
                alert_count += 1

                alert = db_writer.write_alert(scored)

                websocket_server.broadcast(alert)

                print(
                    f"[consumer_v2] [ALERT] "
                    f"#{event_count}  {alert}"
                )

            # Print throughput every 100 events
            # This is independent of whether the event is an alert.
            if event_count % 100 == 0:

                elapsed = time.time() - start_time

                rate = (
                    event_count / elapsed
                    if elapsed > 0
                    else 0
                )

                print(
                    f"[consumer_v2] processed "
                    f"{event_count} events "
                    f"({alert_count} alerts) | "
                    f"{rate:.1f} events/sec"
                )

    except KeyboardInterrupt:

        elapsed = time.time() - start_time

        rate = (
            event_count / elapsed
            if elapsed > 0
            else 0
        )

        print(
            f"\n[consumer_v2] Stopped. "
            f"{event_count} events, "
            f"{alert_count} alerts, "
            f"{elapsed:.1f}s elapsed."
        )

        print(
            f"[consumer_v2] Average throughput: "
            f"{rate:.1f} events/sec"
        )

    finally:
        consumer.close()


if __name__ == "__main__":
    main()