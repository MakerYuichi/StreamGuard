"""
StreamGuard - Streaming vs Batch Comparison

Pulls real streaming results from Postgres (written by consumer_v2.py)
and summarises them.  Precision/recall are not available here because
the scores table has no ground-truth label column by design.

Run from the repo root:
    python -m streamguard.baseline.compare_results
"""

import psycopg2

from streamguard.consumer import config


def get_streaming_results() -> dict:
    conn = psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM scores WHERE src <> 'test_src';")
    total_events = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM alerts WHERE src <> 'test_src';")
    total_alerts = cur.fetchone()[0]

    cur.execute(
        "SELECT src, dst, event_time, score FROM alerts "
        "WHERE src <> 'test_src' ORDER BY event_time ASC;"
    )
    alerts = cur.fetchall()

    cur.execute(
        "SELECT MAX(ingested_at - event_time) FROM scores "
        "WHERE is_alert = TRUE AND src <> 'test_src';"
    )
    max_detection_delay = cur.fetchone()[0]

    cur.execute(
        "SELECT AVG(ingested_at - event_time) FROM scores "
        "WHERE is_alert = TRUE AND src <> 'test_src';"
    )
    avg_detection_delay = cur.fetchone()[0]

    cur.execute(
        "SELECT MIN(anomaly_score), MAX(anomaly_score), AVG(anomaly_score) "
        "FROM scores WHERE src <> 'test_src';"
    )
    min_score, max_score, avg_score = cur.fetchone()

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
    print(f"Maximum detection delay: {results['max_detection_delay']}")
    print(f"Average detection delay: {results['avg_detection_delay']}")
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
            print(f"  {src} -> {dst}  score={score:.2f}  at={event_time}")
    print()
    print(
        "NOTE: Precision and recall cannot be calculated from the current scores "
        "table because ground-truth labels are not stored in PostgreSQL."
    )
