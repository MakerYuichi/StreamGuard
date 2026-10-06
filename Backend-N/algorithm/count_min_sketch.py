"""
StreamGuard - Count-Min Sketch
Based on: Cormode & Muthukrishnan, "An Improved Data Stream Summary:
The Count-Min Sketch and its Applications" (2005).

Fixed-memory, approximate frequency counting. Guarantees: estimated
count overestimates true count by at most (epsilon * N) with
probability (1 - delta), where N = total items added so far.
"""

import hashlib
import math


class CountMinSketch:
    def __init__(self, width: int = 2000, depth: int = 5):
        if width <= 0 or depth <= 0:
            raise ValueError("width and depth must be positive")
        """
        width (w) and depth (d) control the error bound:
          epsilon ~= e / w        (relative error)
          delta   ~= e^(-d)       (failure probability)
        Defaults here give epsilon ~= 0.00136, delta ~= 0.0067 -
        good enough for a 2-day sprint; cite these numbers in your report.
        """
        self.width = width
        self.depth = depth
        self.table = [[0] * width for _ in range(depth)]

    def _hash(self, key: str, row: int) -> int:
        # Different seed per row -> independent-enough hash functions
        h = hashlib.md5(f"{row}-{key}".encode("utf-8")).hexdigest()
        return int(h, 16) % self.width

    def add(self, key: str, count: int = 1):
        if count < 0:
            raise ValueError("Count-Min Sketch only supports non-negative increments")
        for row in range(self.depth):
            col = self._hash(key, row)
            self.table[row][col] += count

    def estimate(self, key: str) -> int:
        return min(self.table[row][self._hash(key, row)] for row in range(self.depth))

    def decay(self, factor: float):
        """Multiply every counter by `factor` (0 < factor < 1) - used
        for the time-decay mechanism so old traffic doesn't permanently
        skew the baseline."""
        if not 0 < factor < 1:
            raise ValueError("factor must be between 0 and 1")
        for row in range(self.depth):
            for col in range(self.width):
                self.table[row][col] = int(self.table[row][col] * factor)

    def error_bound(self, total_items_added: int) -> float:
        """Returns the theoretical max overestimate (epsilon * N) -
        use this number directly in your evaluation section."""
        epsilon = math.e / self.width
        return epsilon * total_items_added
