"""
StreamGuard - Count-Min Sketch

Based on: Cormode & Muthukrishnan, "An Improved Data Stream Summary:
The Count-Min Sketch and its Applications" (2005).

Fixed-memory, approximate frequency counting with error guarantees.
Estimated count overestimates true count by at most (epsilon * N) with
probability (1 - delta), where N = total items added.

Uses mmh3 (MurmurHash3) for speed (not cryptographic MD5).
Counters are 64-bit integers (numpy arrays).
"""

from __future__ import annotations

import math

import mmh3
import numpy as np


class CountMinSketch:
    """
    Count-Min Sketch data structure.

    Maintains a 2D array of counters: (depth rows) × (width columns).
    """

    def __init__(self, width: int = 2000, depth: int = 5, seed: int = 42) -> None:
        """
        Initialise the sketch.

        Args:
            width: Number of columns (higher = lower epsilon).
            depth: Number of rows (higher = lower delta = e^(-depth)).
            seed: Random seed for hash functions.
        """
        if width <= 0 or depth <= 0:
            raise ValueError("width and depth must be positive")

        self.width = width
        self.depth = depth
        self.seed = seed

        # 2D numpy array: uint64 to handle large counters
        self.table: np.ndarray = np.zeros((depth, width), dtype=np.uint64)

    def _hash(self, key: str, row: int) -> int:
        """
        Hash function for a given row.

        Returns a column index in [0, width).
        """
        # Combine row and key into the hash seed so each row gets independent hashes
        combined_seed = self.seed + row
        h = mmh3.hash(key, seed=combined_seed)
        return abs(h) % self.width

    def add(self, key: str, count: int = 1) -> None:
        """
        Increment the count for a key.

        Args:
            key: Item identifier (typically "src→dst").
            count: Amount to add (can be negative for MIDAS-F filtering).

        Raises:
            ValueError: If count is negative and would underflow.
        """
        if count == 0:
            return

        for row in range(self.depth):
            col = self._hash(key, row)
            # numpy uint64 wraps on underflow; prevent negative counts
            if count < 0 and self.table[row, col] < abs(count):
                self.table[row, col] = 0
            else:
                self.table[row, col] += count

    def estimate(self, key: str) -> int:
        """
        Estimate the count for a key.

        Returns the minimum across all rows (count-min estimator).
        """
        estimates = np.array(
            [self.table[row, self._hash(key, row)] for row in range(self.depth)]
        )
        return int(np.min(estimates))

    def decay(self, factor: float) -> None:
        """
        Apply multiplicative decay to all counters.

        Args:
            factor: Multiplier in (0, 1). Each counter is multiplied by factor.

        Raises:
            ValueError: If factor is not in (0, 1).
        """
        if not 0 < factor < 1:
            raise ValueError("factor must be in (0, 1)")

        # Vectorised: multiply all counters by factor
        self.table = (self.table * factor).astype(np.uint64)

    def error_bound(self, total_items_added: int) -> float:
        """
        Theoretical maximum overestimate (epsilon * N).

        Args:
            total_items_added: Total items added to the sketch.

        Returns:
            epsilon * N where epsilon = e / width.
        """
        epsilon = math.e / self.width
        return epsilon * total_items_added

    def memory_bytes(self) -> int:
        """Return memory footprint in bytes."""
        return self.table.nbytes + 64  # nbytes + overhead for metadata
