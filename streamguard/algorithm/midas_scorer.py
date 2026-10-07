"""
StreamGuard - MIDAS-R Streaming Anomaly Scorer

Faithful implementation of MIDAS-R per Bhatia et al., "MIDAS: Microcluster-Based
Detector of Anomalies in Edge Streams" (AAAI 2020, arXiv:2009.08452).

Key differences from the simplified version:
1. Multi-entity scoring: edge, source node, destination node (max of chi-squared scores).
2. Chi-squared formula: ((a - s/t)^2) * t^2 / (s * (t-1)), robust handling of t=1 and s=0.
3. Temporal decay: current-tick counts decay by alpha at tick boundary (MIDAS-R style).
4. Vectorised numpy arrays: fixed memory, fast hashing (mmh3), no Python loops.
5. Detailed output: score, edge_score, src_score, dst_score, counts, tick for explainability.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

import mmh3
import numpy as np

from streamguard.algorithm.count_min_sketch import CountMinSketch


@dataclass
class ScoredEdge:
    """Output of score_edge(). All fields are directly usable for explanations."""

    # Core anomaly detection
    score: float  # max(edge_score, src_score, dst_score)
    is_alert: bool  # score >= anomaly_threshold
    timestamp: int  # unix timestamp (input)

    # Per-entity chi-squared scores for explainability
    edge_score: float
    src_score: float
    dst_score: float

    # Counts that produced the scores
    edge_current: int
    edge_total: int
    src_current: int
    src_total: int
    dst_current: int
    dst_total: int

    # Timing and formula state
    tick: int
    expected_edge: float

    # Input identifiers
    src: str
    dst: str


class MidasScorer:
    """
    MIDAS-R streaming anomaly scorer.

    Maintains Count-Min Sketches for:
    - Current-tick edge/source/destination activity
    - Total (decayed) edge/source/destination activity

    Scores are chi-squared statistics per the MIDAS paper.
    Memory is fixed at construction time (O(depth * width * 3 entities)).
    """

    def __init__(
        self,
        *,
        width: int = 2000,
        depth: int = 5,
        tick_length_seconds: int = 10,
        alpha: float = 0.98,
        anomaly_threshold: float = 3.0,
        use_midas_f_filter: bool = False,
        midas_f_cutoff: float = 1e6,
        seed: int = 42,
    ) -> None:
        """
        Initialise the MIDAS-R scorer.

        Args:
            width: Count-Min Sketch width (higher = lower error).
            depth: Count-Min Sketch depth (higher = lower failure probability).
            tick_length_seconds: Temporal window length.
            alpha: Decay factor in [0, 1) applied to current-tick counts at tick boundary.
            anomaly_threshold: Score >= this is flagged as alert.
            use_midas_f_filter: If True, don't add edges with anomalous scores to total sketches
                               (MIDAS-F style anomaly filtering).
            midas_f_cutoff: Score cutoff above which MIDAS-F filters the edge.
            seed: Random seed for consistent hashing.

        Raises:
            ValueError: If parameters are invalid.
        """
        if width <= 0 or depth <= 0:
            raise ValueError("width and depth must be positive")
        if not 0 <= alpha < 1:
            raise ValueError("alpha must be in [0, 1)")
        if tick_length_seconds <= 0:
            raise ValueError("tick_length_seconds must be positive")
        if anomaly_threshold < 0:
            raise ValueError("anomaly_threshold must be non-negative")

        self.width = width
        self.depth = depth
        self.tick_length_seconds = tick_length_seconds
        self.alpha = alpha
        self.anomaly_threshold = anomaly_threshold
        self.use_midas_f_filter = use_midas_f_filter
        self.midas_f_cutoff = midas_f_cutoff
        self.seed = seed

        # Three pairs of (current_tick, total) sketches: for edge, source, destination
        self.edge_current = CountMinSketch(width, depth, seed=seed)
        self.edge_total = CountMinSketch(width, depth, seed=seed + 1)

        self.src_current = CountMinSketch(width, depth, seed=seed + 2)
        self.src_total = CountMinSketch(width, depth, seed=seed + 3)

        self.dst_current = CountMinSketch(width, depth, seed=seed + 4)
        self.dst_total = CountMinSketch(width, depth, seed=seed + 5)

        # Temporal bookkeeping
        self.start_time: int | None = None
        self.current_tick = 0
        self.total_items_added = 0

    def _tick_for_timestamp(self, timestamp: int) -> int:
        """
        Map a unix timestamp to a tick index.

        Tick 1 is the first window, tick 2 the second, etc.
        """
        timestamp = int(timestamp)
        if self.start_time is None:
            self.start_time = timestamp
        elapsed = max(0, timestamp - self.start_time)
        return max(1, elapsed // self.tick_length_seconds + 1)

    def _decay_all(self) -> None:
        """Apply alpha decay to all current-tick sketches (MIDAS-R)."""
        self.edge_current.decay(self.alpha)
        self.src_current.decay(self.alpha)
        self.dst_current.decay(self.alpha)

    def _chi_squared(self, current: int, total: int, tick: int) -> float:
        """
        Compute chi-squared anomaly score.

        Formula from MIDAS paper (Equation 1):
            score = ((a - s/t)^2) * t^2 / (s * (t-1))
        where:
            a = current count
            s = total count
            t = tick

        Safeguards:
        - If s = 0, return 0 (no history → no anomaly).
        - If t = 1, return 0 (first tick, no baseline).
        - Avoid division by zero.
        """
        if total <= 0 or tick <= 1:
            return 0.0
        if current <= 0:
            return 0.0

        expected = total / tick
        numerator = (current - expected) ** 2 * tick * tick
        denominator = total * (tick - 1)

        # Avoid division by zero
        if denominator <= 0:
            return 0.0

        return numerator / denominator

    def score_edge(self, src: str, dst: str, timestamp: int) -> ScoredEdge:
        """
        Score a single edge in the stream.

        Args:
            src: Source node identifier.
            dst: Destination node identifier.
            timestamp: Unix timestamp (seconds).

        Returns:
            ScoredEdge dataclass with detailed scores and counts for explainability.
        """
        timestamp = int(timestamp)
        tick = self._tick_for_timestamp(timestamp)

        # Tick boundary: decay current sketches and reset for new tick
        if tick > self.current_tick:
            if self.current_tick > 0:
                self._decay_all()
            # After decay, current sketches naturally accumulate new events in this tick
            self.current_tick = tick

        # Increment counts in all sketches
        self.edge_current.add(f"{src}→{dst}")
        self.src_current.add(src)
        self.dst_current.add(dst)

        self.edge_total.add(f"{src}→{dst}")
        self.src_total.add(src)
        self.dst_total.add(dst)

        self.total_items_added += 1

        # Query counts
        edge_current = self.edge_current.estimate(f"{src}→{dst}")
        edge_total = self.edge_total.estimate(f"{src}→{dst}")

        src_current = self.src_current.estimate(src)
        src_total = self.src_total.estimate(src)

        dst_current = self.dst_current.estimate(dst)
        dst_total = self.dst_total.estimate(dst)

        # Compute chi-squared scores
        edge_score = self._chi_squared(edge_current, edge_total, tick)
        src_score = self._chi_squared(src_current, src_total, tick)
        dst_score = self._chi_squared(dst_current, dst_total, tick)

        # Overall score is maximum (any entity can trigger alert)
        score = max(edge_score, src_score, dst_score)

        # MIDAS-F filter (optional): don't propagate anomalous edges to total sketches
        if self.use_midas_f_filter and score > self.midas_f_cutoff:
            # Undo the additions to total sketches for this edge
            self.edge_total.add(f"{src}→{dst}", -1)
            self.src_total.add(src, -1)
            self.dst_total.add(dst, -1)

        expected_edge = edge_total / tick if tick > 0 else 0.0

        return ScoredEdge(
            score=score,
            is_alert=score >= self.anomaly_threshold,
            timestamp=timestamp,
            edge_score=edge_score,
            src_score=src_score,
            dst_score=dst_score,
            edge_current=edge_current,
            edge_total=edge_total,
            src_current=src_current,
            src_total=src_total,
            dst_current=dst_current,
            dst_total=dst_total,
            tick=tick,
            expected_edge=expected_edge,
            src=src,
            dst=dst,
        )

    def memory_bytes(self) -> int:
        """
        Return the fixed memory footprint in bytes.

        6 sketches × (width × depth × 8 bytes per counter) + overhead.
        """
        sketch_bytes = 6 * self.width * self.depth * 8
        overhead = 256  # Rough estimate for Python object overhead
        return sketch_bytes + overhead

    def error_bound(self) -> tuple[float, float]:
        """
        Return theoretical error bounds for Count-Min Sketch.

        Returns (epsilon, delta) where:
        - epsilon ≈ e / width (relative error)
        - delta ≈ e^(-depth) (failure probability)
        """
        import math

        epsilon = math.e / self.width
        delta = math.exp(-self.depth)
        return epsilon, delta

    def to_dict(self) -> dict[str, Any]:
        """Return scorer config as a dict (for serialization / reporting)."""
        return {
            "width": self.width,
            "depth": self.depth,
            "tick_length_seconds": self.tick_length_seconds,
            "alpha": self.alpha,
            "anomaly_threshold": self.anomaly_threshold,
            "use_midas_f_filter": self.use_midas_f_filter,
            "midas_f_cutoff": self.midas_f_cutoff,
            "seed": self.seed,
            "total_items_added": self.total_items_added,
            "current_tick": self.current_tick,
            "memory_bytes": self.memory_bytes(),
        }
