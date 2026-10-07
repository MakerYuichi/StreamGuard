"""
CIC-IDS2017 Dataset Loader

Loads the CIC-IDS2017 labelled-flows CSVs (with source/destination IPs).
Cleans data, normalises labels, and writes to parquet for efficient streaming.

Usage:
    loader = CICIDSLoader()
    df = loader.load('data/cic-ids2017/*.csv')
    loader.to_parquet('data/processed/cic-ids2017.parquet')

    # Or use the replayer:
    python -m streamguard.ingestion.cicids2017_replayer \\
        data/processed/cic-ids2017.parquet --rate 100 --sample 10000
"""

from __future__ import annotations

import glob
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class CICIDSLoader:
    """Load and clean CIC-IDS2017 flow data."""

    # CIC-IDS2017 label normalisation (handle variations)
    LABEL_MAPPING = {
        "BENIGN": "Benign",
        "benign": "Benign",
        "Benign": "Benign",
        # DDoS
        "DDoS": "DDoS",
        "DDOS": "DDoS",
        # Port scanning
        "Port Scan": "PortScan",
        "port scan": "PortScan",
        "PortScan": "PortScan",
        # Bot
        "Bot": "Bot",
        "BOT": "Bot",
        "Botnet": "Bot",
        # Brute Force
        "SSH-Bruteforce": "BruteForce-SSH",
        "Brute Force": "BruteForce",
        "brute force": "BruteForce",
        # Web attacks
        "Web Attack - Brute Force": "WebAttack-BruteForce",
        "Web Attack - XSS": "WebAttack-XSS",
        "Web Attack - Sql Injection": "WebAttack-SQLi",
        # Infiltration
        "Infiltration": "Infiltration",
        # DoS
        "DoS Hulk": "DoS-Hulk",
        "DoS Slowhttptest": "DoS-Slowhttptest",
        "DoS Slowloris": "DoS-Slowloris",
        "DoS GoldenEye": "DoS-GoldenEye",
    }

    # Numeric feature columns (expected in CIC-IDS2017)
    NUMERIC_FEATURES = [
        "Flow Duration",
        "Total Fwd Packets",
        "Total Bwd Packets",
        "Total Length of Fwd Packets",
        "Total Length of Bwd Packets",
        "Fwd Packet Length Max",
        "Fwd Packet Length Min",
        "Fwd Packet Length Mean",
        "Fwd Packet Length Std",
        "Bwd Packet Length Max",
        "Bwd Packet Length Min",
        "Bwd Packet Length Mean",
        "Bwd Packet Length Std",
        "Flow Bytes/s",
        "Flow Packets/s",
        "Flow IAT Mean",
        "Flow IAT Std",
        "Flow IAT Max",
        "Flow IAT Min",
        "Fwd IAT Total",
        "Fwd IAT Mean",
        "Fwd IAT Std",
        "Fwd IAT Max",
        "Fwd IAT Min",
        "Bwd IAT Total",
        "Bwd IAT Mean",
        "Bwd IAT Std",
        "Bwd IAT Max",
        "Bwd IAT Min",
        "Fwd PSH Flags",
        "Bwd PSH Flags",
        "Fwd URG Flags",
        "Bwd URG Flags",
        "Fwd Header Length",
        "Bwd Header Length",
        "Fwd Packets/s",
        "Bwd Packets/s",
        "Min Packet Length",
        "Max Packet Length",
        "Packet Length Mean",
        "Packet Length Std",
        "Packet Length Variance",
        "FIN Flag Count",
        "SYN Flag Count",
        "RST Flag Count",
        "PSH Flag Count",
        "ACK Flag Count",
        "URG Flag Count",
        "CWE Flag Count",
        "ECE Flag Count",
        "Down/Up Ratio",
        "Average Packet Size",
        "Avg Fwd Segment Size",
        "Avg Bwd Segment Size",
        "Fwd Header Length",
        "Fwd Avg Bytes/Bulk",
        "Fwd Avg Packets/Bulk",
        "Fwd Avg Bulk Rate",
        "Bwd Avg Bytes/Bulk",
        "Bwd Avg Packets/Bulk",
        "Bwd Avg Bulk Rate",
        "Subflow Fwd Packets",
        "Subflow Fwd Bytes",
        "Subflow Bwd Packets",
        "Subflow Bwd Bytes",
        "Init_Win_bytes_forward",
        "Init_Win_bytes_backward",
        "act_data_pkt_fwd",
        "min_seg_size_forward",
        "Active Mean",
        "Active Std",
        "Active Max",
        "Active Min",
        "Idle Mean",
        "Idle Std",
        "Idle Max",
        "Idle Min",
    ]

    def __init__(self) -> None:
        self.df: pd.DataFrame | None = None
        self.raw_files: list[str] = []

    def load(self, pattern: str, sample: int | None = None) -> pd.DataFrame:
        """
        Load CIC-IDS2017 CSVs matching a glob pattern.

        Args:
            pattern: Glob pattern for CSV files (e.g., 'data/cic-ids2017/*.csv')
            sample: If set, sample this many rows per file before combining

        Returns:
            Cleaned dataframe with added is_attack and attack_type columns
        """
        self.raw_files = sorted(glob.glob(pattern))
        if not self.raw_files:
            raise FileNotFoundError(f"No files found matching {pattern}")

        dfs = []
        for fpath in self.raw_files:
            print(f"Loading {Path(fpath).name}...")
            df = pd.read_csv(fpath)
            if sample and len(df) > sample:
                df = df.sample(n=sample, random_state=42)
            dfs.append(df)

        combined = pd.concat(dfs, ignore_index=True)
        self.df = self._clean(combined)
        return self.df

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean the dataframe.

        - Strip column names
        - Normalise label
        - Handle inf/NaN in numeric columns
        - Parse timestamps
        - Drop duplicates
        - Add is_attack and attack_type
        """
        # Strip column names
        df.columns = df.columns.str.strip()

        # Normalise and create label columns
        if "Label" not in df.columns:
            raise ValueError("'Label' column not found")

        df["Label"] = df["Label"].str.strip().map(self.LABEL_MAPPING)
        if df["Label"].isna().any():
            print(f"Warning: {df['Label'].isna().sum()} unknown labels (set to Benign)")
            df["Label"].fillna("Benign", inplace=True)

        df["is_attack"] = df["Label"] != "Benign"
        df["attack_type"] = df["Label"].where(df["is_attack"], "Benign")

        # Handle inf and NaN in numeric features
        numeric_cols = [col for col in self.NUMERIC_FEATURES if col in df.columns]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                # Replace inf with NaN then fill with column median
                df[col] = df[col].replace([np.inf, -np.inf], np.nan)
                median_val = df[col].median()
                df[col].fillna(median_val, inplace=True)

        # Parse timestamps (CIC-IDS2017 uses various formats)
        if "Timestamp" in df.columns:
            df["Timestamp"] = self._parse_timestamps(df["Timestamp"])

        # Drop exact duplicates (but keep duplicate flows if timestamps differ)
        df = df.drop_duplicates(
            subset=[col for col in df.columns if col not in ["Timestamp"]],
            keep="first",
        )

        # Sort by timestamp
        if "Timestamp" in df.columns:
            df = df.sort_values("Timestamp").reset_index(drop=True)

        return df

    def _parse_timestamps(self, ts_series: pd.Series) -> pd.Series:
        """
        Parse various timestamp formats in CIC-IDS2017.

        Handles AM/PM ambiguity by attempting multiple formats.
        """
        # Try common formats
        for fmt in [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %I:%M:%S %p",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %I:%M:%S %p",
        ]:
            try:
                return pd.to_datetime(ts_series, format=fmt, errors="coerce")
            except Exception:
                continue

        # Fallback: try pandas inference (slower but more flexible)
        print("Warning: using pandas timestamp inference (slower)")
        return pd.to_datetime(ts_series, errors="coerce")

    def to_parquet(self, path: str) -> None:
        """
        Write cleaned dataframe to parquet.

        Args:
            path: Output path for parquet file
        """
        if self.df is None:
            raise ValueError("No data loaded. Call load() first.")

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.df.to_parquet(path, index=False, compression="snappy")
        print(f"Wrote {len(self.df)} rows to {path}")

    def describe(self) -> dict[str, Any]:
        """Return summary statistics about the loaded data."""
        if self.df is None:
            raise ValueError("No data loaded")

        return {
            "total_rows": len(self.df),
            "benign_rows": (~self.df["is_attack"]).sum(),
            "attack_rows": self.df["is_attack"].sum(),
            "attack_types": self.df["attack_type"].value_counts().to_dict(),
            "numeric_columns": len([c for c in self.NUMERIC_FEATURES if c in self.df.columns]),
            "files_loaded": len(self.raw_files),
        }


def main() -> None:
    """CLI entry point for loading CIC-IDS2017."""
    import argparse

    parser = argparse.ArgumentParser(description="Load and clean CIC-IDS2017 dataset")
    parser.add_argument("pattern", help="Glob pattern for CSV files")
    parser.add_argument("--output", default="data/processed/cic-ids2017.parquet")
    parser.add_argument("--sample", type=int, default=None, help="Sample N rows per file")
    args = parser.parse_args()

    loader = CICIDSLoader()
    df = loader.load(args.pattern, sample=args.sample)
    print("\nSummary:")
    for key, val in loader.describe().items():
        print(f"  {key}: {val}")

    loader.to_parquet(args.output)


if __name__ == "__main__":
    main()
