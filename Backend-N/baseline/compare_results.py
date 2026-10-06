"""
StreamGuard - Streaming vs Batch Comparison

Pulls real streaming results from Postgres (written by
consumer_v2.py) and compares them against the batch baseline.

The scores table does NOT contain a ground-truth `label` column,
so precision/recall cannot be calculated from Postgres alone.
"""

import psycopg2
from pathlib import Path
import sys

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "consumer")
)

import config


def get_streaming_results():
    conn = psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )

    cur = conn.cursor()

    # ---------------------------------------------------------
    # Total events
    # ---------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*)
        FROM scores
        WHERE src <> 'test_src';
    """)

    total_events = cur.fetchone()[0]

    # ---------------------------------------------------------
    # Total alerts
    # ---------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*)
        FROM alerts
        WHERE src <> 'test_src';
    """)

    total_alerts = cur.fetchone()[0]

    # ---------------------------------------------------------
    # Alert details
    # ---------------------------------------------------------

    cur.execute("""
        SELECT
            src,
            dst,
            event_time,
            score
        FROM alerts
        WHERE src <> 'test_src'
        ORDER BY event_time ASC;
    """)

    alerts = cur.fetchall()

    # ---------------------------------------------------------
    # Detection delay
    #
    # ingested_at is the database insertion time.
    # event_time is the timestamp from the original event.
    # ---------------------------------------------------------

    cur.execute("""
        SELECT
            MAX(ingested_at - event_time)
        FROM scores
        WHERE is_alert = TRUE
          AND src <> 'test_src';
    """)

    max_detection_delay = cur.fetchone()[0]

    # ---------------------------------------------------------
    # Average detection delay
    # ---------------------------------------------------------

    cur.execute("""
        SELECT
            AVG(ingested_at - event_time)
        FROM scores
        WHERE is_alert = TRUE
          AND src <> 'test_src';
    """)

    avg_detection_delay = cur.fetchone()[0]

    # ---------------------------------------------------------
    # Score statistics
    # ---------------------------------------------------------

    cur.execute("""
        SELECT
            MIN(anomaly_score),
            MAX(anomaly_score),
            AVG(anomaly_score)
        FROM scores
        WHERE src <> 'test_src';
    """)

    min_score, max_score, avg_score = cur.fetchone()

    # ---------------------------------------------------------
    # Close DB connection
    # ---------------------------------------------------------

    cur.close()
    conn.close()

    return {
        "total_events": total_events,
        "total_alerts": total_alerts,
        "alerts": alerts,
        "max_detection_delay": max_detection_delay,
        "avg_detection_delay": avg_detection_delay,
        "min_score": min_score,
        "max_score": max_score,
        "avg_score": avg_score,
    }


if __name__ == "__main__":

    results = get_streaming_results()

    print()
    print("=== STREAMING ENGINE (StreamGuard / MIDAS) ===")
    print()

    print(f"Total events processed: {results['total_events']}")
    print(f"Total alerts raised:    {results['total_alerts']}")

    print()
    print("=== DETECTION LATENCY ===")

    print(
        f"Maximum detection delay: "
        f"{results['max_detection_delay']}"
    )

    print(
        f"Average detection delay: "
        f"{results['avg_detection_delay']}"
    )

    print()
    print("=== ANOMALY SCORE STATISTICS ===")

    print(f"Minimum score: {results['min_score']}")
    print(f"Maximum score: {results['max_score']}")
    print(f"Average score: {results['avg_score']}")

    print()
    print("=== ALERTS ===")

    if not results["alerts"]:
        print("No alerts raised.")

    else:
        for src, dst, event_time, score in results["alerts"]:
            print(
                f"  {src} -> {dst}  "
                f"score={score:.2f}  "
                f"at={event_time}"
            )

    print()
    print("=== BATCH COMPARISON ===")
    print()

    print(
        "Compare these results against baseline_batch.py:"
    )

    print(
        "  1. Detection delay:"
        " streaming should detect anomalies immediately,"
        " while batch processing waits for its window."
    )

    print(
        "  2. Alert count:"
        " compare the number of streaming alerts"
        " against the batch baseline."
    )

    print(
        "  3. Anomaly scores:"
        " compare MIDAS streaming scores"
        " against the batch implementation."
    )

    print(
        "  4. Memory:"
        " MIDAS maintains fixed-size sketch state"
        " instead of storing the entire stream."
    )

    print()
    print(
        "NOTE: Precision and recall cannot be calculated from"
        " the current scores table because ground-truth labels"
        " are not stored in PostgreSQL."
    )