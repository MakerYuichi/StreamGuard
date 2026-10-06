"""
StreamGuard - Naive Batch Baseline (updated for DARPA compatibility)
-------------------------------------------------------------------
Usage:
    # fake_traffic.csv style (embedded label column, has header)
    python baseline_batch.py fake_traffic.csv --window 10 --zthresh 2.5

    # real DARPA style (separate headerless files)
    python baseline_batch.py ../data/darpa_processed.csv --no-header \
        --window 10 --zthresh 2.5 --ground-truth ../data/darpa_ground_truth.csv
"""

import argparse
import pandas as pd
import numpy as np

from ground_truth import load_true_attack_edges


def run_baseline(csv_path: str, window_seconds: int, z_threshold: float,
                  no_header: bool = False, ground_truth_csv: str = None):

    # --- Load the raw edge data (WITHOUT requiring a label column) ---
    if ground_truth_csv or no_header:
        df = pd.read_csv(csv_path, header=None, names=["src", "dst", "timestamp"])
    else:
        df = pd.read_csv(csv_path)  # expects src,dst,timestamp,label header

    df["src"] = df["src"].astype(str)
    df["dst"] = df["dst"].astype(str)
    df = df.sort_values("timestamp").reset_index(drop=True)

    t_min = df["timestamp"].min()
    t_max = df["timestamp"].max()

    print(f"[baseline] Loaded {len(df)} rows, time range {t_min} -> {t_max} "
          f"({t_max - t_min}s)")
    print(f"[baseline] Window size: {window_seconds}s | z-score threshold: {z_threshold}\n")

    df["bucket"] = ((df["timestamp"] - t_min) // window_seconds).astype(int)

    flagged_rows = []

    for bucket_id in sorted(df["bucket"].unique()):
        current_window = df[df["bucket"] == bucket_id]
        history_before = df[df["bucket"] < bucket_id]

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
    flagged_edges = set(
        tuple(x) for x in flagged_df[["src", "dst"]].drop_duplicates().values
    ) if len(flagged_df) > 0 else set()

    print(f"[baseline] Total windows processed: {df['bucket'].nunique()}")
    print(f"[baseline] Total anomalies flagged (events): {len(flagged_df)}")
    print(f"[baseline] Total anomalies flagged (unique edges): {len(flagged_edges)}\n")

    # --- Ground truth: from the ORIGINAL dataset/label files, never from Postgres ---
    true_attack_edges = load_true_attack_edges(csv_path, ground_truth_csv, no_header)

    true_positives = true_attack_edges & flagged_edges
    precision = len(true_positives) / len(flagged_edges) if flagged_edges else 0.0
    recall = len(true_positives) / len(true_attack_edges) if true_attack_edges else 0.0

    print(f"[baseline] Ground truth attack edges: {len(true_attack_edges)}")
    print(f"[baseline] Correctly caught (true positives): {len(true_positives)}")
    print(f"[baseline] Precision: {precision:.3f} | Recall: {recall:.3f}")

    return {
        "flagged_edges": flagged_edges,
        "true_attack_edges": true_attack_edges,
        "true_positives": true_positives,
        "precision": precision,
        "recall": recall,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Naive batch anomaly baseline")
    parser.add_argument("csv_path", help="path to the edge-stream CSV")
    parser.add_argument("--window", type=int, default=10, help="time window size in seconds")
    parser.add_argument("--zthresh", type=float, default=2.5, help="z-score threshold for flagging")
    parser.add_argument("--no-header", action="store_true", help="set if csv_path has NO header row")
    parser.add_argument("--ground-truth", default=None,
                         help="path to a separate headerless label file (DARPA-style). "
                              "If omitted, csv_path must have an embedded `label` column.")
    args = parser.parse_args()

    run_baseline(args.csv_path, args.window, args.zthresh, args.no_header, args.ground_truth)