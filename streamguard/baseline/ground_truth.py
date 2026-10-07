"""
StreamGuard - Ground Truth Loader
Shared by baseline_batch.py and compare_final.py so both pull
attack-edge ground truth the EXACT same way, from the ORIGINAL
input dataset/label files -- never from Postgres (Postgres has no
label column, intentionally, per the production schema decision).

Supports two formats:
  1. Single CSV with an embedded `label` column (fake_traffic.csv style)
     - may or may not have a header row
  2. Two separate files (real DARPA style)
     - data file: headerless, columns = src,dst,timestamp
     - ground truth file: headerless, single column = label
     - aligned by row order (line N in data = line N in ground truth)
"""

import pandas as pd


def load_true_attack_edges(data_csv: str, ground_truth_csv: str = None, no_header: bool = False) -> set:
    """
    Returns a set of (src, dst) string tuples for every edge that
    has at least one row labeled as an attack (label == 1).
    """
    if ground_truth_csv:
        # DARPA-style: two separate headerless files, aligned by row position
        data = pd.read_csv(data_csv, header=None, names=["src", "dst", "timestamp"])
        labels = pd.read_csv(ground_truth_csv, header=None, names=["label"])

        if len(data) != len(labels):
            raise ValueError(
                f"Row count mismatch: data has {len(data)} rows, "
                f"ground truth has {len(labels)} rows. They must be aligned 1:1 "
                f"-- re-check your downloads."
            )

        data["label"] = labels["label"]

    else:
        # fake_traffic.csv style: label embedded in the same file
        if no_header:
            data = pd.read_csv(data_csv, header=None, names=["src", "dst", "timestamp", "label"])
        else:
            data = pd.read_csv(data_csv)

    data["src"] = data["src"].astype(str)
    data["dst"] = data["dst"].astype(str)

    attack_rows = data[data["label"] == 1]
    attack_edges = set(
        tuple(x) for x in attack_rows[["src", "dst"]].drop_duplicates().values
    )
    return attack_edges