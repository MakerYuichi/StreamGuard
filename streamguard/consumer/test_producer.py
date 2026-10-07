"""
StreamGuard - Phase 1 Test Producer
-------------------------------------
Purpose: prove the Kafka pipe works, independent of the real DARPA
replayer (Role 2's job) and independent of the real scoring function
(Role 1's job).

Run this, then run consumer_skeleton.py in another terminal - you
should see the fake events printed there within a second or two.

Usage:
    python test_producer.py
    python test_producer.py --count 50 --delay 0.2
"""

import argparse
import json
import random
import time

from kafka import KafkaProducer

from streamguard.consumer import config


def make_fake_event(i: int) -> dict:
    """
    Builds one fake raw event matching the INPUT shape the real
    DARPA replayer (Role 2) will eventually send.
    This is NOT the scored-event contract yet - scoring happens
    downstream, inside the consumer / Role 1's function.
    """
    return {
        "src": f"192.168.1.{random.randint(1, 20)}",
        "dst": f"10.0.0.{random.randint(1, 20)}",
        "timestamp": int(time.time()),
    }


def main():
    parser = argparse.ArgumentParser(description="Push fake test events into Kafka")
    parser.add_argument("--count", type=int, default=20, help="number of fake events to send")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between each event")
    args = parser.parse_args()

    print(f"[test_producer] Connecting to Kafka at {config.KAFKA_BOOTSTRAP_SERVERS} ...")

    producer = KafkaProducer(
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    print(f"[test_producer] Connected. Sending {args.count} fake events to topic '{config.KAFKA_TOPIC}' ...")

    for i in range(args.count):
        event = make_fake_event(i)
        producer.send(config.KAFKA_TOPIC, value=event)
        print(f"[test_producer] sent #{i+1}: {event}")
        time.sleep(args.delay)

    producer.flush()
    print("[test_producer] Done. All events flushed to Kafka.")


if __name__ == "__main__":
    main()
