"""
StreamGuard - Naive Batch Baseline (Role 5, Phase 1)
-------------------------------------------------------
This is the "dumb" comparison point for the real streaming engine.
It does NOT stream -- it re-reads the data in fixed time windows
and recomputes frequency counts from scratch each time, which is
exactly the batch-style weakness we're trying to show the real
system avoids.

Usage:
    python baseline_batch.py fake_traffic.csv
    python baseline_batch.py fake_traffic.csv --window 10 --zthresh 2.5
"""

import argparse
import pandas as pd
import numpy as np


def run_baseline(csv_path: str, window_seconds: int, z_threshold: float):
    df = pd.read_csv(csv_path)
    df = df.sort_values("timestamp").reset_index(drop=True)

    t_min = df["timestamp"].min()
    t_max = df["timestamp"].max()

    print(f"[baseline] Loaded {len(df)} rows, time range {t_min} -> {t_max} "
          f"({t_max - t_min}s)")
    print(f"[baseline] Window size: {window_seconds}s | z-score threshold: {z_threshold}\n")

    # Assign every row to a time bucket
    df["bucket"] = ((df["timestamp"] - t_min) // window_seconds).astype(int)

    flagged_rows = []
    detection_log = []  # (bucket_number, bucket_end_time) for each flagged edge - used for "delay" measurement

    # Running history of (src,dst) pair counts per bucket, built up
    # as we go -- this simulates "recompute stats from the full
    # history available up to now" at each window boundary.
    seen_so_far = pd.DataFrame(columns=["src", "dst", "bucket"])

    for bucket_id in sorted(df["bucket"].unique()):
        current_window = df[df["bucket"] == bucket_id]
        history_before = df[df["bucket"] < bucket_id]

        # Recompute edge frequency counts using ALL history before this window
        # (this re-scan is deliberately expensive/batch-y -- that's the point)
        if len(history_before) > 0:
            hist_counts = history_before.groupby(["src", "dst"]).size()
            mean_count = hist_counts.mean()
            std_count = hist_counts.std() if hist_counts.std() > 0 else 1.0
        else:
            mean_count = 0
            std_count = 1.0

        current_counts = current_window.groupby(["src", "dst"]).size()

        for (src, dst), count in current_counts.items():
            z_score = (count - mean_count) / std_count
            if z_score >= z_threshold:
                bucket_end_time = t_min + (bucket_id + 1) * window_seconds
                flagged_rows.append({
                    "src": src, "dst": dst, "bucket": bucket_id,
                    "count_in_window": count, "z_score": round(z_score, 2),
                    "flagged_at_time": bucket_end_time,
                })

    flagged_df = pd.DataFrame(flagged_rows)

    print(f"[baseline] Total windows processed: {df['bucket'].nunique()}")
    print(f"[baseline] Total anomalies flagged: {len(flagged_df)}\n")

    if len(flagged_df) > 0:
        print("[baseline] Flagged edges:")
        print(flagged_df.to_string(index=False))
    else:
        print("[baseline] No anomalies flagged -- try lowering --zthresh")

    # If the data has ground-truth labels, report basic accuracy
    if "label" in df.columns:
        true_attack_edges = set(
            tuple(x) for x in df[df["label"] == 1][["src", "dst"]].drop_duplicates().values
        )
        flagged_edges = set(
            tuple(x) for x in flagged_df[["src", "dst"]].drop_duplicates().values
        ) if len(flagged_df) > 0 else set()

        true_positives = true_attack_edges & flagged_edges
        print(f"\n[baseline] Ground truth attack edges: {true_attack_edges}")
        print(f"[baseline] Correctly caught: {true_positives}")
        print(f"[baseline] Precision-ish: {len(true_positives)}/{len(flagged_edges) or 1} "
              f"| Recall-ish: {len(true_positives)}/{len(true_attack_edges) or 1}")

    return flagged_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Naive batch anomaly baseline")
    parser.add_argument("csv_path", help="path to the edge-stream CSV")
    parser.add_argument("--window", type=int, default=10, help="time window size in seconds")
    parser.add_argument("--zthresh", type=float, default=2.5, help="z-score threshold for flagging")
    args = parser.parse_args()

    run_baseline(args.csv_path, args.window, args.zthresh)