#!/usr/bin/env python3
"""
Attribute Analysis for CIC-IDS2017

Analyzes feature distributions, importance, and attack signatures.
Generates data-backed detection rules for each attack type.

Output:
  - results/attribute_table.csv: Summary of per-attack-type rules
  - results/attribute_analysis.md: Detailed findings
  - results/feature_importance.csv: Feature importance rankings
  - results/correlation_heatmap.png: Feature correlation heatmap

Usage:
    python scripts/attribute_analysis.py \\
        --input data/processed/cic-ids2017.parquet \\
        --output results/

Or via Makefile:
    make attributes

Requires:
  - pandas, numpy
  - scikit-learn (for decision trees, mutual info, feature importance)
  - matplotlib, seaborn (for heatmap visualization)
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import recall_score, precision_score
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

# ── Top features for focus (chosen to minimize analysis runtime while capturing key signals)
TOP_FEATURES = [
    "Flow Duration",
    "Total Fwd Packets",
    "Total Bwd Packets",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Fwd Packet Length Mean",
    "Bwd Packet Length Mean",
    "Packet Length Mean",
    "Flow IAT Mean",
    "Fwd IAT Mean",
    "Bwd IAT Mean",
    "FIN Flag Count",
    "SYN Flag Count",
    "RST Flag Count",
    "ACK Flag Count",
    "Fwd PSH Flags",
    "Bwd PSH Flags",
    "Down/Up Ratio",
    "Average Packet Size",
    "Init_Win_bytes_forward",
]


def compute_feature_statistics(
    df: pd.DataFrame, attack_types: list[str]
) -> pd.DataFrame:
    """
    Compute per-attack-type feature statistics.

    Returns a DataFrame with columns:
      - attack_type
      - feature
      - benign_median, benign_iqr
      - attack_median, attack_iqr
      - effect_size (cliff's delta)
      - discrimination_power (0-1, higher = more discriminative)
    """
    results = []

    for attack in attack_types:
        benign_data = df[df["attack_type"] == "Benign"]
        attack_data = df[df["attack_type"] == attack]

        for feature in TOP_FEATURES:
            if feature not in df.columns:
                continue

            benign_vals = benign_data[feature].dropna()
            attack_vals = attack_data[feature].dropna()

            if len(benign_vals) == 0 or len(attack_vals) == 0:
                continue

            # Basic statistics
            benign_median = float(benign_vals.median())
            benign_iqr = float(benign_vals.quantile(0.75) - benign_vals.quantile(0.25))
            attack_median = float(attack_vals.median())
            attack_iqr = float(attack_vals.quantile(0.75) - attack_vals.quantile(0.25))

            # Effect size: Cliff's delta (simpler than Cohen's d for non-normal data)
            cliff_delta = _cliff_delta(benign_vals.values, attack_vals.values)

            # Discrimination power: normalized distance between medians
            max_range = max(
                benign_vals.max() - benign_vals.min(),
                attack_vals.max() - attack_vals.min(),
            )
            if max_range > 0:
                discrimination = abs(attack_median - benign_median) / max_range
            else:
                discrimination = 0.0

            results.append(
                {
                    "attack_type": attack,
                    "feature": feature,
                    "benign_median": benign_median,
                    "benign_iqr": benign_iqr,
                    "attack_median": attack_median,
                    "attack_iqr": attack_iqr,
                    "cliff_delta": cliff_delta,
                    "discrimination": discrimination,
                }
            )

    return pd.DataFrame(results)


def _cliff_delta(x: np.ndarray, y: np.ndarray) -> float:
    """
    Compute Cliff's delta effect size.

    Range: [-1, 1]. Values > 0.5 indicate large effect.
    """
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return 0.0

    # Count dominance: how often x > y vs y > x
    greater = sum(x[:, None] > y[None, :])
    less = sum(x[:, None] < y[None, :])

    delta = (greater - less) / (n1 * n2)
    return float(delta)


def compute_feature_importance(df: pd.DataFrame, attack_types: list[str]) -> dict[str, list]:
    """
    Compute feature importance for each attack type using mutual information.

    Returns dict mapping attack_type -> list of (feature, importance_score) tuples.
    """
    importance_dict: dict[str, list] = {}

    # Encode attack_type as numeric labels
    label_encoder = LabelEncoder()
    df["label_numeric"] = label_encoder.fit_transform(df["attack_type"])

    for attack in attack_types:
        # Binary classification: this attack vs. not
        y_binary = (df["attack_type"] == attack).astype(int)

        if y_binary.sum() < 10:  # Skip if too few samples
            continue

        # Compute mutual information for top features
        feature_scores = []
        for feature in TOP_FEATURES:
            if feature not in df.columns or df[feature].isna().all():
                continue

            x_vals = df[feature].fillna(df[feature].median()).values

            # Discretize for mutual info (5 bins)
            x_discrete = pd.qcut(x_vals, q=5, labels=False, duplicates="drop")
            mi = _mutual_information(x_discrete, y_binary.values)
            feature_scores.append((feature, mi))

        # Sort by importance and keep top 10
        feature_scores.sort(key=lambda t: t[1], reverse=True)
        importance_dict[attack] = feature_scores[:10]

    return importance_dict


def _mutual_information(x: np.ndarray, y: np.ndarray) -> float:
    """Compute mutual information between two discrete variables."""
    # Joint entropy
    joint_counts = np.column_stack((x, y))
    _, joint_counts = np.unique(joint_counts, axis=0, return_counts=True)
    joint_prob = joint_counts / len(x)
    joint_entropy = -np.sum(joint_prob * np.log2(joint_prob + 1e-10))

    # Marginal entropies
    x_unique, x_counts = np.unique(x, return_counts=True)
    x_prob = x_counts / len(x)
    x_entropy = -np.sum(x_prob * np.log2(x_prob + 1e-10))

    y_unique, y_counts = np.unique(y, return_counts=True)
    y_prob = y_counts / len(y)
    y_entropy = -np.sum(y_prob * np.log2(y_prob + 1e-10))

    mi = x_entropy + y_entropy - joint_entropy
    return float(max(0.0, mi))  # Ensure non-negative


def build_decision_trees(df: pd.DataFrame, attack_types: list[str]) -> dict[str, Any]:
    """
    Build shallow decision trees (depth ≤ 3) for each attack type.

    Returns dict mapping attack_type -> {
        'tree': DecisionTreeClassifier,
        'feature_importance': list,
        'rules': list of (feature, threshold, direction) tuples,
        'accuracy': float,
        'precision': float,
        'recall': float,
    }
    """
    trees = {}
    label_encoder = LabelEncoder()
    df["label_numeric"] = label_encoder.fit_transform(df["attack_type"])

    for attack in attack_types:
        # Prepare binary classification data
        y = (df["attack_type"] == attack).astype(int)
        if y.sum() < 20:  # Skip if too few positive samples
            continue

        # Select features
        X = df[TOP_FEATURES].fillna(df[TOP_FEATURES].median())
        X = X[[col for col in TOP_FEATURES if col in X.columns]]

        if X.shape[1] == 0:
            continue

        # Train shallow tree
        tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=10, random_state=42)
        tree.fit(X, y)

        # Extract rules (simplified: just look at first few splits)
        rules = _extract_rules_from_tree(tree, X.columns.tolist())

        # Evaluate
        y_pred = tree.predict(X)
        accuracy = float((y_pred == y).mean())
        precision = float(precision_score(y, y_pred, zero_division=0))
        recall = float(recall_score(y, y_pred, zero_division=0))

        trees[attack] = {
            "tree": tree,
            "feature_importance": list(zip(X.columns, tree.feature_importances_)),
            "rules": rules,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
        }

    return trees


def _extract_rules_from_tree(
    tree: DecisionTreeClassifier, feature_names: list[str]
) -> list[tuple]:
    """Extract simple rules from tree (first few levels)."""
    rules = []

    def traverse(node: int, depth: int) -> None:
        if depth > 2:  # Limit depth for readability
            return

        feature_idx = tree.tree_.feature[node]
        threshold = tree.tree_.threshold[node]

        if feature_idx >= 0:
            feature = feature_names[feature_idx]
            rules.append((feature, float(threshold), "<="))
            rules.append((feature, float(threshold), ">"))

        # Traverse children
        left_child = tree.tree_.children_left[node]
        right_child = tree.tree_.children_right[node]
        if left_child != -1:
            traverse(left_child, depth + 1)
        if right_child != -1:
            traverse(right_child, depth + 1)

    traverse(0, 0)
    return rules


def compute_correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Compute correlation matrix for top features."""
    features = [f for f in TOP_FEATURES if f in df.columns]
    X = df[features].fillna(df[features].median())
    return X.corr()


def generate_attribute_table(
    df: pd.DataFrame,
    feature_stats: pd.DataFrame,
    trees: dict[str, Any],
    importance_dict: dict[str, list],
) -> pd.DataFrame:
    """
    Generate final attribute table with suggested detection rules.

    Columns:
      - attack_type
      - key_features (top 3 discriminators)
      - benign_range (median ± IQR)
      - attack_range (median ± IQR)
      - suggested_rule
      - support (% of attack samples)
      - rule_precision
      - rule_recall
    """
    rows = []

    for attack in trees.keys():
        # Get most discriminative features
        attack_stats = feature_stats[feature_stats["attack_type"] == attack].sort_values(
            "discrimination", ascending=False
        )
        top_features = attack_stats.head(3)["feature"].tolist()

        # Build suggested rule string
        if len(top_features) > 0:
            feature = top_features[0]
            f_stats = feature_stats[
                (feature_stats["attack_type"] == attack)
                & (feature_stats["feature"] == feature)
            ]
            if len(f_stats) > 0:
                attack_median = f_stats.iloc[0]["attack_median"]
                attack_iqr = f_stats.iloc[0]["attack_iqr"]
                benign_median = f_stats.iloc[0]["benign_median"]

                # Rule: if this feature is outside benign range, flag as attack
                benign_min = benign_median - benign_median * 0.5
                benign_max = benign_median + benign_median * 0.5 if benign_median > 0 else 1.0

                if attack_median > benign_max:
                    suggested_rule = f"{feature} > {benign_max:.2f}"
                elif attack_median < benign_min:
                    suggested_rule = f"{feature} < {benign_min:.2f}"
                else:
                    suggested_rule = f"{feature} in anomaly distribution"
            else:
                suggested_rule = "Insufficient data"
        else:
            suggested_rule = "No discriminative features"

        # Get support (% of samples in dataset)
        attack_count = (df["attack_type"] == attack).sum()
        total_count = len(df)
        support = (attack_count / total_count * 100) if total_count > 0 else 0.0

        # Get precision/recall from tree
        tree_info = trees.get(attack, {})
        precision = tree_info.get("precision", 0.0)
        recall = tree_info.get("recall", 0.0)

        # Build range strings
        top_feat_ranges = []
        for feat in top_features[:2]:
            feat_stats = feature_stats[
                (feature_stats["attack_type"] == attack) & (feature_stats["feature"] == feat)
            ]
            if len(feat_stats) > 0:
                benign_med = feat_stats.iloc[0]["benign_median"]
                benign_iqr = feat_stats.iloc[0]["benign_iqr"]
                attack_med = feat_stats.iloc[0]["attack_median"]
                attack_iqr = feat_stats.iloc[0]["attack_iqr"]
                benign_range = f"{benign_med:.0f}±{benign_iqr:.0f}"
                attack_range = f"{attack_med:.0f}±{attack_iqr:.0f}"
                top_feat_ranges.append((feat, benign_range, attack_range))

        rows.append(
            {
                "attack_type": attack,
                "key_features": ", ".join(top_features[:3]),
                "benign_range": top_feat_ranges[0][1] if top_feat_ranges else "N/A",
                "attack_range": top_feat_ranges[0][2] if top_feat_ranges else "N/A",
                "suggested_rule": suggested_rule,
                "support_percent": support,
                "rule_precision": precision,
                "rule_recall": recall,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze CIC-IDS2017 attributes")
    parser.add_argument(
        "--input",
        default="data/processed/cic-ids2017.parquet",
        help="Path to input parquet file",
    )
    parser.add_argument(
        "--output", default="results/", help="Output directory for results"
    )
    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    df = pd.read_parquet(args.input)
    print(f"Loaded {len(df)} rows with columns: {list(df.columns)}")

    attack_types = [t for t in df["attack_type"].unique() if t != "Benign"]
    print(f"Attack types: {attack_types}")

    print("\n[1] Computing feature statistics...")
    feature_stats = compute_feature_statistics(df, attack_types)

    print(f"[2] Computing feature importance for {len(attack_types)} attack types...")
    importance_dict = compute_feature_importance(df, attack_types)

    print("[3] Building decision trees...")
    trees = build_decision_trees(df, attack_types)

    print("[4] Computing correlation matrix...")
    corr_matrix = compute_correlation_matrix(df)

    print("[5] Generating attribute table...")
    attr_table = generate_attribute_table(df, feature_stats, trees, importance_dict)

    # Save results
    print("\n[SAVE] Attribute table...")
    attr_table.to_csv(output_dir / "attribute_table.csv", index=False)
    print(f"  → {output_dir / 'attribute_table.csv'}")

    print("[SAVE] Feature statistics...")
    feature_stats.to_csv(output_dir / "feature_statistics.csv", index=False)
    print(f"  → {output_dir / 'feature_statistics.csv'}")

    print("[SAVE] Feature importance...")
    importance_out = []
    for attack, features in importance_dict.items():
        for rank, (feature, score) in enumerate(features, 1):
            importance_out.append(
                {
                    "attack_type": attack,
                    "rank": rank,
                    "feature": feature,
                    "importance": score,
                }
            )
    pd.DataFrame(importance_out).to_csv(output_dir / "feature_importance.csv", index=False)
    print(f"  → {output_dir / 'feature_importance.csv'}")

    print("[SAVE] Correlation heatmap...")
    plt.figure(figsize=(12, 10))
    sns.heatmap(
        corr_matrix,
        cmap="coolwarm",
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        annot=False,
    )
    plt.title("Feature Correlation Matrix (CIC-IDS2017)")
    plt.tight_layout()
    plt.savefig(output_dir / "correlation_heatmap.png", dpi=150)
    plt.close()
    print(f"  → {output_dir / 'correlation_heatmap.png'}")

    # Generate markdown report
    print("[SAVE] Markdown report...")
    with open(output_dir / "attribute_analysis.md", "w") as f:
        f.write("# Attribute Analysis Report: CIC-IDS2017\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Total rows: {len(df)}\n")
        f.write(f"- Attack types: {len(attack_types)}\n")
        f.write(f"- Features analyzed: {len(TOP_FEATURES)}\n\n")

        f.write("## Attack Type Statistics\n\n")
        for _, row in attr_table.iterrows():
            f.write(f"### {row['attack_type']}\n\n")
            f.write(f"- **Key Features**: {row['key_features']}\n")
            f.write(f"- **Support**: {row['support_percent']:.2f}%\n")
            f.write(f"- **Tree Precision**: {row['rule_precision']:.3f}\n")
            f.write(f"- **Tree Recall**: {row['rule_recall']:.3f}\n")
            f.write(f"- **Suggested Rule**: `{row['suggested_rule']}`\n\n")

        f.write("## Feature Importance Rankings\n\n")
        for attack, features in sorted(importance_dict.items()):
            if features:
                f.write(f"### {attack}\n\n")
                for rank, (feature, score) in enumerate(features[:5], 1):
                    f.write(f"{rank}. {feature} (MI: {score:.4f})\n")
                f.write("\n")

        f.write("## Decision Tree Insights\n\n")
        for attack, tree_info in sorted(trees.items()):
            f.write(f"### {attack}\n\n")
            f.write(f"- **Accuracy**: {tree_info['accuracy']:.3f}\n")
            f.write(f"- **Precision**: {tree_info['precision']:.3f}\n")
            f.write(f"- **Recall**: {tree_info['recall']:.3f}\n")
            f.write("\n")

    print(f"  → {output_dir / 'attribute_analysis.md'}")

    print("\n✓ Attribute analysis complete!")
    print(f"\nOutputs in {output_dir}/:")
    print("  - attribute_table.csv (main results)")
    print("  - feature_statistics.csv (per-feature stats)")
    print("  - feature_importance.csv (MI rankings)")
    print("  - correlation_heatmap.png (feature correlations)")
    print("  - attribute_analysis.md (detailed report)")


if __name__ == "__main__":
    main()
