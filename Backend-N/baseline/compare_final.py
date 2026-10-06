"""
StreamGuard - Final Apples-to-Apples Comparison
--------------------------------------------------
Compares BATCH (naive z-score) vs STREAMING (real MIDAS, already run
and sitting in Postgres) on the SAME dataset, using the SAME
edge-level ground truth, loaded from the ORIGINAL dataset files.

Key correction from earlier: streaming alerts are DEDUPLICATED to
unique (src,dst) edges before scoring precision/recall, because one
anomalous edge can legitimately produce many alert rows over time
(one per event), while the batch baseline already evaluates at the
unique-edge level. Comparing event-count to edge-count was the bug.

Usage:
    python compare_final.py ../data/darpa_processed.csv --no-header \
        --ground-truth ../data/darpa_ground_truth.csv --window 10 --zthresh 2.5
"""

import argparse
import sys

import psycopg2

sys.path.append("../consumer")
import config

from ground_truth import load_true_attack_edges
from baseline_batch import run_baseline


def get_streaming_flagged_edges() -> set:
    """
    Pulls the set of UNIQUE (src, dst) edges that the real streaming
    MIDAS engine flagged as alerts, from Postgres. This is the fix --
    previously every alert ROW was being treated as a separate
    detection; here we collapse to distinct edges to match how the
    batch baseline evaluates.
    """
    conn = psycopg2.connect(
        host=config.POSTGRES_HOST, port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB, user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT src, dst FROM alerts;")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return set((str(src), str(dst)) for src, dst in rows)


def get_streaming_total_alert_events() -> int:
    """For reference only -- shows how many raw alert ROWS existed
    before dedup, so you can report the before/after in your writeup."""
    conn = psycopg2.connect(
        host=config.POSTGRES_HOST, port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB, user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM alerts;")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return total


def main():
    parser = argparse.ArgumentParser(description="Final batch vs streaming comparison")
    parser.add_argument("csv_path", help="path to the dataset that was streamed")
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--zthresh", type=float, default=2.5)
    parser.add_argument("--no-header", action="store_true")
    parser.add_argument("--ground-truth", default=None)
    args = parser.parse_args()

    print("=" * 60)
    print("STEP 1: Running batch baseline on the same dataset")
    print("=" * 60)
    batch_result = run_baseline(
        args.csv_path, args.window, args.zthresh, args.no_header, args.ground_truth
    )

    print("\n" + "=" * 60)
    print("STEP 2: Pulling streaming engine results from Postgres")
    print("=" * 60)
    raw_alert_events = get_streaming_total_alert_events()
    streaming_flagged_edges = get_streaming_flagged_edges()
    print(f"[streaming] Raw alert EVENTS in Postgres: {raw_alert_events}")
    print(f"[streaming] Deduplicated to UNIQUE EDGES: {len(streaming_flagged_edges)}")

    print("\n" + "=" * 60)
    print("STEP 3: Ground truth (same source used for both)")
    print("=" * 60)
    true_attack_edges = load_true_attack_edges(args.csv_path, args.ground_truth, args.no_header)
    print(f"[ground truth] Total true attack edges: {len(true_attack_edges)}")

    streaming_tp = streaming_flagged_edges & true_attack_edges
    streaming_precision = len(streaming_tp) / len(streaming_flagged_edges) if streaming_flagged_edges else 0.0
    streaming_recall = len(streaming_tp) / len(true_attack_edges) if true_attack_edges else 0.0

    print("\n" + "=" * 60)
    print("FINAL COMPARISON")
    print("=" * 60)
    print(f"{'Metric':<30} {'Batch':>12} {'Streaming':>12}")
    print(f"{'-'*30} {'-'*12} {'-'*12}")
    print(f"{'Flagged edges':<30} {len(batch_result['flagged_edges']):>12} {len(streaming_flagged_edges):>12}")
    print(f"{'True positives':<30} {len(batch_result['true_positives']):>12} {len(streaming_tp):>12}")
    print(f"{'Precision':<30} {batch_result['precision']:>12.3f} {streaming_precision:>12.3f}")
    print(f"{'Recall':<30} {batch_result['recall']:>12.3f} {streaming_recall:>12.3f}")
    print(f"\nNote: streaming engine raised {raw_alert_events} total alert EVENTS,")
    print(f"collapsed to {len(streaming_flagged_edges)} unique edges for this comparison.")


if __name__ == "__main__":
    main()