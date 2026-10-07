"""
StreamGuard - Phase 1 Consumer Skeleton
-------------------------------------------
PHASE 1 GOAL (this file): prove the Kafka pipe works end-to-end.
  Connect to Kafka -> read events off the topic -> print them.
  No scoring, no DB writes, no WebSocket yet - that's Phase 2.

PHASE 2 (next person / next session) will extend this file to:
  1. Import Role 1's real scoring function (replace `fake_score_event` below)
  2. Write every scored event into the `scores` table (see db_writer.py stub)
  3. When is_alert=True, also write to the `alerts` table
  4. Push alerts out over a WebSocket (see websocket_server.py stub)

Run this AFTER starting test_producer.py in another terminal (or
in the same terminal in the background) to see it working.

Usage:
    python consumer_skeleton.py
"""

import json
import time

from kafka import KafkaConsumer

from streamguard.consumer import config


def fake_score_event(event: dict) -> dict:
    """
    PLACEHOLDER scoring function for Phase 1.
    Role 1 will replace the body of this function (or you'll import
    their real module here) with the actual Count-Min Sketch +
    chi-squared scoring logic in Phase 2.

    Input:  {"src": str, "dst": str, "timestamp": int}
    Output: matches the agreed "Scored Event" contract:
            {"src", "dst", "timestamp", "anomaly_score", "is_alert"}
    """
    # Dummy logic just so the pipeline shape is provably correct end-to-end.
    # DO NOT treat this as real anomaly detection - it's a stand-in.
    fake_score = hash((event["src"], event["dst"])) % 10  # 0-9, deterministic-ish
    return {
        "src": event["src"],
        "dst": event["dst"],
        "timestamp": event["timestamp"],
        "anomaly_score": float(fake_score),
        "is_alert": fake_score >= config.ANOMALY_THRESHOLD,
    }


def main():
    print(f"[consumer] Connecting to Kafka at {config.KAFKA_BOOTSTRAP_SERVERS} ...")

    consumer = KafkaConsumer(
        config.KAFKA_TOPIC,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",   # read from the beginning of the topic
        enable_auto_commit=True,
        group_id="streamguard-consumer-group",
    )

    print(f"[consumer] Connected. Listening on topic '{config.KAFKA_TOPIC}' ... (Ctrl+C to stop)")
    print(f"[consumer] NOTE: using PLACEHOLDER scoring (fake_score_event) - not real detection yet.\n")

    event_count = 0
    alert_count = 0
    start_time = time.time()

    try:
        for message in consumer:
            raw_event = message.value
            scored = fake_score_event(raw_event)

            event_count += 1
            if scored["is_alert"]:
                alert_count += 1

            tag = "ALERT" if scored["is_alert"] else "ok   "
            print(f"[consumer] [{tag}] #{event_count}  {scored}")

            # --- Phase 2 will add here: ---
            # db_writer.write_score(scored)
            # if scored["is_alert"]:
            #     alert = db_writer.write_alert(scored)
            #     websocket_server.broadcast(alert)

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n[consumer] Stopped. Processed {event_count} events "
              f"({alert_count} alerts) in {elapsed:.1f}s.")


if __name__ == "__main__":
    main()
