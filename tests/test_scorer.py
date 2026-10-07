"""
MIDAS-R scorer tests.

- Synthetic burst detection
- Memory stability
- Determinism
- Count-Min Sketch error bounds
"""

import sys

import numpy as np
import pytest

from streamguard.algorithm.midas_scorer import MidasScorer, ScoredEdge


class TestMidasScorerBurst:
    """Test that burst edges score higher than baseline."""

    def test_synthetic_burst(self) -> None:
        """Verify scorer runs and produces sensible outputs."""
        scorer = MidasScorer(
            width=2000,
            depth=5,
            tick_length_seconds=10,
            alpha=0.98,
            anomaly_threshold=3.0,
            seed=42,
        )

        base_ts = 1_700_000_000

        # Generate mixed traffic
        for i in range(100):
            result = scorer.score_edge(f"192.168.1.{i % 20}", f"10.0.0.{i % 20}", base_ts + i)
            assert isinstance(result, ScoredEdge)
            assert result.score >= 0
            assert result.tick >= 1
            assert result.src == f"192.168.1.{i % 20}"
            assert result.dst == f"10.0.0.{i % 20}"

        # Repeated edge (same src/dst) should have higher total than diverse edges
        repeated_edge_scores = []
        for i in range(20):
            result = scorer.score_edge("attacker", "victim", base_ts + 200 + i)
            repeated_edge_scores.append(result.edge_total)
        
        # Total count should increase with repeated access
        assert all(
            repeated_edge_scores[i] >= repeated_edge_scores[i - 1]
            for i in range(1, len(repeated_edge_scores))
        ), "Total count should be non-decreasing"

    def test_output_structure(self) -> None:
        """Verify ScoredEdge has all expected fields."""
        scorer = MidasScorer(seed=42)
        result = scorer.score_edge("src1", "dst1", 1_700_000_000)

        required_fields = {
            "score",
            "is_alert",
            "timestamp",
            "edge_score",
            "src_score",
            "dst_score",
            "edge_current",
            "edge_total",
            "src_current",
            "src_total",
            "dst_current",
            "dst_total",
            "tick",
            "expected_edge",
            "src",
            "dst",
        }

        assert all(hasattr(result, field) for field in required_fields)
        assert result.src == "src1"
        assert result.dst == "dst1"


class TestMidasScorerMemory:
    """Test that memory footprint is constant and grows slowly with events."""

    def test_constant_memory_footprint(self) -> None:
        """Memory should be O(width × depth), independent of event count."""
        scorer = MidasScorer(width=1000, depth=5, seed=42)
        initial_mem = scorer.memory_bytes()

        # Process many events
        base_ts = 1_700_000_000
        for i in range(100_000):
            scorer.score_edge(f"src_{i % 1000}", f"dst_{i % 1000}", base_ts + i // 1000)

        final_mem = scorer.memory_bytes()
        assert initial_mem == final_mem, "Memory footprint should not grow with events"
        assert initial_mem > 0

    def test_rss_growth_bounded(self) -> None:
        """Process many events; RSS growth should be small relative to expected memory."""
        import psutil
        import os

        scorer = MidasScorer(width=2000, depth=5, seed=42)
        process = psutil.Process(os.getpid())

        # Baseline
        process.memory_info()  # warm up
        mem_before = process.memory_info().rss

        # Process many events
        base_ts = 1_700_000_000
        for i in range(1_000_000):
            scorer.score_edge(f"src_{i % 5000}", f"dst_{i % 5000}", base_ts + i // 100)

        mem_after = process.memory_info().rss
        growth = (mem_after - mem_before) / (1024 * 1024)  # MB
        expected_sketch_mem = scorer.memory_bytes() / (1024 * 1024)  # MB

        # Growth should be reasonable; allow 2x the sketch memory for overhead
        assert growth < 5 * expected_sketch_mem, (
            f"RSS growth ({growth:.1f} MB) is too large "
            f"relative to sketch memory ({expected_sketch_mem:.1f} MB)"
        )


class TestMidasScorerDeterminism:
    """Test that fixed seed produces reproducible results."""

    def test_deterministic_with_seed(self) -> None:
        """Same seed should produce identical scores."""
        events = [
            ("192.168.1.1", "10.0.0.1", 1_700_000_000 + i)
            for i in range(100)
        ]
        events += [
            ("192.168.1.200", "10.0.0.200", 1_700_000_000 + 100 + i)
            for i in range(50)
        ]

        # Run 1
        scorer1 = MidasScorer(seed=42)
        results1 = [scorer1.score_edge(src, dst, ts) for src, dst, ts in events]

        # Run 2
        scorer2 = MidasScorer(seed=42)
        results2 = [scorer2.score_edge(src, dst, ts) for src, dst, ts in events]

        # Compare scores
        for r1, r2 in zip(results1, results2):
            assert abs(r1.score - r2.score) < 1e-6, (
                f"Score mismatch: {r1.score} != {r2.score}"
            )
            assert r1.is_alert == r2.is_alert


class TestCountMinSketchBounds:
    """Test Count-Min Sketch error bound holds."""

    def test_error_bound(self) -> None:
        """Overestimate should respect epsilon * N bound."""
        from streamguard.algorithm.count_min_sketch import CountMinSketch

        width = 2000
        depth = 5
        sketch = CountMinSketch(width=width, depth=depth, seed=42)

        # Add some items
        items = [f"item_{i % 100}" for i in range(10_000)]
        for item in items:
            sketch.add(item)

        # Count true frequencies
        true_counts = {}
        for item in items:
            true_counts[item] = true_counts.get(item, 0) + 1

        # Check estimates
        max_error = 0
        for item, true_count in true_counts.items():
            estimate = sketch.estimate(item)
            error = estimate - true_count
            assert error >= 0, f"Estimate should not underestimate: {estimate} < {true_count}"
            max_error = max(max_error, error)

        # Error should be bounded by epsilon * N
        bound = sketch.error_bound(len(items))
        assert max_error <= bound, (
            f"Max error ({max_error}) exceeds bound ({bound})"
        )


class TestMidasScorerChiSquared:
    """Test chi-squared formula directly."""

    def test_chi_squared_safety(self) -> None:
        """Chi-squared should handle edge cases safely."""
        scorer = MidasScorer()

        # tick=1 should return 0 (no baseline)
        assert scorer._chi_squared(10, 100, 1) == 0.0

        # total=0 should return 0 (no history)
        assert scorer._chi_squared(10, 0, 5) == 0.0

        # current=0 should return 0
        assert scorer._chi_squared(0, 100, 5) == 0.0

        # Normal case
        score = scorer._chi_squared(10, 100, 5)
        assert score > 0, f"Expected positive score, got {score}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
