#!/usr/bin/env python3
"""
Load CIC-IDS2017 CSVs and convert to Parquet.

This is a helper script for Docker to load the dataset.
"""

from __future__ import annotations

import glob
import os
import sys

# Add /app to path so imports work
sys.path.insert(0, '/app')

from streamguard.ingestion.cicids2017 import CICIDSLoader


def main() -> None:
    """Load CSVs and convert to parquet."""
    print("[1] Scanning for CIC-IDS2017 CSV files...")
    
    # Look in multiple possible locations (including with trailing space!)
    search_patterns = [
        "data/TrafficLabelling/*ISCX.csv",
        "data/TrafficLabelling */*ISCX.csv",  # Handle trailing space in dirname
        "data/cic-ids2017/*.csv",
    ]
    
    files = []
    for pattern in search_patterns:
        found = sorted(glob.glob(pattern))
        files.extend(found)
        if found:
            print(f"     Found files via pattern: {pattern}")
    
    files = sorted(set(files))  # Remove duplicates and sort
    
    if not files:
        print("ERROR: No CIC-IDS2017 CSV files found")
        print("Expected: data/TrafficLabelling/*ISCX.csv or data/cic-ids2017/*.csv")
        print("Please download GeneratedLabelledFlows.zip from https://www.unb.ca/cic/datasets/ids-2017.html")
        sys.exit(1)
    
    print(f"[2] Found {len(files)} files:")
    for f in files:
        print(f"     - {f}")
    
    print("[3] Loading and cleaning data...")
    loader = CICIDSLoader()
    
    # Load using glob pattern (first pattern that found files)
    if files:
        first_file = files[0]
        if "TrafficLabelling" in first_file:
            pattern = "data/TrafficLabelling */*ISCX.csv"
        else:
            pattern = "data/cic-ids2017/*.csv"
    else:
        pattern = search_patterns[0]
    
    df = loader.load(pattern)
    print(f"     Loaded {len(df)} rows")
    
    print("[4] Converting to Parquet...")
    os.makedirs("data/processed", exist_ok=True)
    loader.to_parquet("data/processed/cic-ids2017.parquet")
    
    print("[5] Summary:")
    desc = loader.describe()
    for key, val in desc.items():
        print(f"     {key}: {val}")
    
    print("\n✓ Parquet file ready: data/processed/cic-ids2017.parquet")


if __name__ == "__main__":
    main()
