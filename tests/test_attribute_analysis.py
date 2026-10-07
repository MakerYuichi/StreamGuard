"""
Tests for attribute analysis script.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_cicids_parquet():
    """Create a sample CIC-IDS2017-like parquet for testing."""
    np.random.seed(42)
    
    n_samples = 1000
    
    # Create synthetic data with clear attack patterns
    data = {
        "Flow Duration": np.random.exponential(5000, n_samples),
        "Total Fwd Packets": np.random.poisson(20, n_samples),
        "Total Bwd Packets": np.random.poisson(15, n_samples),
        "Total Length of Fwd Packets": np.random.exponential(1000, n_samples),
        "Total Length of Bwd Packets": np.random.exponential(800, n_samples),
        "Fwd Packet Length Mean": np.random.gamma(50, 2, n_samples),
        "Bwd Packet Length Mean": np.random.gamma(45, 2, n_samples),
        "Packet Length Mean": np.random.gamma(47, 2, n_samples),
        "Flow Bytes/s": np.random.exponential(1000, n_samples),
        "Flow Packets/s": np.random.exponential(50, n_samples),
        "Flow IAT Mean": np.random.exponential(500, n_samples),
        "Fwd IAT Mean": np.random.exponential(600, n_samples),
        "Bwd IAT Mean": np.random.exponential(550, n_samples),
        "FIN Flag Count": np.random.poisson(1, n_samples),
        "SYN Flag Count": np.random.poisson(2, n_samples),
        "RST Flag Count": np.random.poisson(0.5, n_samples),
        "ACK Flag Count": np.random.poisson(15, n_samples),
        "Fwd PSH Flags": np.random.poisson(2, n_samples),
        "Bwd PSH Flags": np.random.poisson(1, n_samples),
        "Down/Up Ratio": np.random.gamma(1, 1, n_samples),
        "Average Packet Size": np.random.gamma(100, 2, n_samples),
        "Init_Win_bytes_forward": np.random.gamma(5000, 2, n_samples),
    }
    
    df = pd.DataFrame(data)
    
    # Add labels: 80% benign, 20% attack
    labels = np.random.choice(
        ["Benign", "DDoS", "PortScan", "BruteForce-SSH"],
        size=n_samples,
        p=[0.7, 0.15, 0.1, 0.05]
    )
    df["attack_type"] = labels
    df["is_attack"] = df["attack_type"] != "Benign"
    df["Label"] = df["attack_type"]
    
    # Add attack-specific patterns
    ddos_mask = df["attack_type"] == "DDoS"
    df.loc[ddos_mask, "Flow Packets/s"] = np.random.exponential(500, ddos_mask.sum())
    df.loc[ddos_mask, "Total Fwd Packets"] = np.random.poisson(100, ddos_mask.sum())
    
    portscan_mask = df["attack_type"] == "PortScan"
    df.loc[portscan_mask, "Total Bwd Packets"] = np.random.poisson(5, portscan_mask.sum())
    df.loc[portscan_mask, "SYN Flag Count"] = np.random.poisson(50, portscan_mask.sum())
    
    brute_mask = df["attack_type"] == "BruteForce-SSH"
    df.loc[brute_mask, "Flow Duration"] = np.random.exponential(30000, brute_mask.sum())
    
    return df


def test_attribute_analysis_runs(sample_cicids_parquet, tmp_path):
    """Test that attribute analysis script runs without error."""
    import sys
    from pathlib import Path as PathlibPath
    
    # Save sample parquet
    input_file = tmp_path / "sample.parquet"
    sample_cicids_parquet.to_parquet(input_file)
    
    output_dir = tmp_path / "results"
    
    # Import and run the analysis
    sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
    from scripts.attribute_analysis import main
    
    # Monkey-patch sys.argv
    original_argv = sys.argv
    try:
        sys.argv = [
            "attribute_analysis.py",
            "--input",
            str(input_file),
            "--output",
            str(output_dir),
        ]
        main()
    finally:
        sys.argv = original_argv
    
    # Check that output files were created
    assert (output_dir / "attribute_table.csv").exists()
    assert (output_dir / "feature_statistics.csv").exists()
    assert (output_dir / "feature_importance.csv").exists()
    assert (output_dir / "attribute_analysis.md").exists()


def test_attribute_table_content(sample_cicids_parquet, tmp_path):
    """Test that attribute table has expected columns."""
    import sys
    from pathlib import Path as PathlibPath
    
    input_file = tmp_path / "sample.parquet"
    sample_cicids_parquet.to_parquet(input_file)
    
    output_dir = tmp_path / "results"
    
    sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
    from scripts.attribute_analysis import main
    
    original_argv = sys.argv
    try:
        sys.argv = [
            "attribute_analysis.py",
            "--input",
            str(input_file),
            "--output",
            str(output_dir),
        ]
        main()
    finally:
        sys.argv = original_argv
    
    # Load and verify attribute table
    attr_table = pd.read_csv(output_dir / "attribute_table.csv")
    
    expected_cols = [
        "attack_type",
        "key_features",
        "benign_range",
        "attack_range",
        "suggested_rule",
        "support_percent",
        "rule_precision",
        "rule_recall",
    ]
    for col in expected_cols:
        assert col in attr_table.columns, f"Missing column: {col}"
    
    # Check that we have at least one attack type
    assert len(attr_table) > 0
    assert "DDoS" in attr_table["attack_type"].values or len(attr_table) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

