"""
StreamGuard - Phase 2 Consumer
Real scoring (MIDAS) + DB writes + WebSocket broadcast, all wired together.

Run from the repo root:
    python -m streamguard.consumer.consumer_v2
"""

import json
import time

from kafka import KafkaConsumer

from streamguard.config import settings
from streamguard.consumer import config, db_writer, websocket_server
from streamguard.algorithm.midas_scorer import MidasScorer


def main() -> None:
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
        tick_length_seconds=settings.tick_length_seconds,
        width=settings.sketch_width,
        depth=settings.sketch_depth,
        history_decay=settings.history_decay,
        anomaly_threshold=settings.anomaly_threshold,
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
                raw["timestamp"],
            )

            if raw.get("label") is not None:
                scored["label"] = int(raw["label"])

            event_count += 1

            db_writer.write_score(scored)

            if scored["is_alert"]:
                alert_count += 1
                alert = db_writer.write_alert(scored)
                websocket_server.broadcast(alert)
                print(f"[consumer_v2] [ALERT] #{event_count}  {alert}")

            if event_count % 100 == 0:
                elapsed = time.time() - start_time
                rate = event_count / elapsed if elapsed > 0 else 0
                print(
                    f"[consumer_v2] processed {event_count} events "
                    f"({alert_count} alerts) | {rate:.1f} events/sec"
                )

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        rate = event_count / elapsed if elapsed > 0 else 0
        print(
            f"\n[consumer_v2] Stopped. "
            f"{event_count} events, {alert_count} alerts, {elapsed:.1f}s elapsed."
        )
        print(f"[consumer_v2] Average throughput: {rate:.1f} events/sec")

    finally:
        consumer.close()


if __name__ == "__main__":
    main()
