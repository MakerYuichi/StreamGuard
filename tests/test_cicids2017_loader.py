"""
Tests for CIC-IDS2017 loader.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from streamguard.ingestion.cicids2017 import CICIDSLoader


@pytest.fixture
def sample_cicids_csv() -> pd.DataFrame:
    """Create a minimal CIC-IDS2017-like sample."""
    data = {
        "Source IP": ["192.168.1.1", "192.168.1.2", "192.168.1.1"],
        "Destination IP": ["10.0.0.1", "10.0.0.2", "10.0.0.1"],
        "Source Port": [12345, 54321, 12345],
        "Destination Port": [80, 443, 80],
        "Protocol": [6, 6, 6],
        "Timestamp": ["2023-01-01 10:00:00", "2023-01-01 10:00:01", "2023-01-01 10:00:02"],
        "Flow Duration": [1000, 2000, 1500],
        "Total Fwd Packets": [10, 20, 15],
        "Total Bwd Packets": [5, 10, 8],
        "Total Length of Fwd Packets": [500, 1000, 750],
        "Total Length of Bwd Packets": [200, 400, 300],
        "Fwd Packet Length Mean": [50.0, 50.0, 50.0],
        "Fwd Packet Length Std": [5.0, 5.0, 5.0],
        "Flow Bytes/s": [700, 1400, 1050],
        "Flow Packets/s": [15, 30, 23],
        "Flow IAT Mean": [100, 100, 100],
        "Flow IAT Std": [10, 10, 10],
        "FIN Flag Count": [0, 0, 0],
        "SYN Flag Count": [1, 1, 1],
        "RST Flag Count": [0, 0, 0],
        "ACK Flag Count": [5, 10, 8],
        "Label": ["BENIGN", "DDoS", "BENIGN"],
    }
    return pd.DataFrame(data)


def test_loader_loads_and_cleans(sample_cicids_csv, tmp_path):
    """Test that loader loads, cleans, and adds attack columns."""
    csv_path = tmp_path / "sample.csv"
    sample_cicids_csv.to_csv(csv_path, index=False)

    loader = CICIDSLoader()
    df = loader.load(str(tmp_path / "*.csv"))

    # Check basic structure
    assert len(df) == 3
    assert "is_attack" in df.columns
    assert "attack_type" in df.columns
    assert "Label" in df.columns

    # Check label normalisation
    assert df["Label"].unique().tolist() == ["Benign", "DDoS"]

    # Check is_attack
    assert df["is_attack"].tolist() == [False, True, False]

    # Check attack_type
    assert df["attack_type"].tolist() == ["Benign", "DDoS", "Benign"]


def test_loader_handles_inf_and_nan(tmp_path):
    """Test that inf and NaN are handled."""
    data = {
        "Source IP": ["192.168.1.1", "192.168.1.2"],
        "Destination IP": ["10.0.0.1", "10.0.0.2"],
        "Timestamp": ["2023-01-01 10:00:00", "2023-01-01 10:00:01"],
        "Flow Duration": [1000, float("inf")],
        "Total Fwd Packets": [10, 20],
        "Flow Bytes/s": [700, float("nan")],
        "Label": ["BENIGN", "BENIGN"],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "sample.csv"
    df.to_csv(csv_path, index=False)

    loader = CICIDSLoader()
    result = loader.load(str(tmp_path / "*.csv"))

    # Check no inf or NaN remain in numeric columns
    numeric_cols = [c for c in result.columns if result[c].dtype in ["float64", "int64"]]
    assert not result[numeric_cols].isin([float("inf"), float("-inf")]).any().any()


def test_loader_to_parquet(sample_cicids_csv, tmp_path):
    """Test writing to parquet."""
    csv_path = tmp_path / "sample.csv"
    sample_cicids_csv.to_csv(csv_path, index=False)

    parquet_path = tmp_path / "output.parquet"

    loader = CICIDSLoader()
    loader.load(str(tmp_path / "*.csv"))
    loader.to_parquet(str(parquet_path))

    assert parquet_path.exists()

    # Verify parquet can be read
    df = pd.read_parquet(str(parquet_path))
    assert len(df) == 3
    assert "is_attack" in df.columns


def test_loader_describe(sample_cicids_csv, tmp_path):
    """Test summary statistics."""
    csv_path = tmp_path / "sample.csv"
    sample_cicids_csv.to_csv(csv_path, index=False)

    loader = CICIDSLoader()
    loader.load(str(tmp_path / "*.csv"))
    desc = loader.describe()

    assert desc["total_rows"] == 3
    assert desc["benign_rows"] == 2
    assert desc["attack_rows"] == 1
    assert "DDoS" in desc["attack_types"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
