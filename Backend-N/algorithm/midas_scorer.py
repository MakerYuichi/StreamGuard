"""Bounded-memory Count-Min-Sketch burst heuristic inspired by MIDAS.

This is a simplified heuristic, not a full reproduction of the paper's
microcluster detector.
"""
from algorithm.count_min_sketch import CountMinSketch

ANOMALY_THRESHOLD = 3.0


class MidasScorer:
    def __init__(self, tick_length_seconds=10, width=2000, depth=5,
                 history_decay=0.98, anomaly_threshold=ANOMALY_THRESHOLD):
        if tick_length_seconds <= 0:
            raise ValueError("tick_length_seconds must be positive")
        if not 0 < history_decay < 1:
            raise ValueError("history_decay must be between 0 and 1")
        self.tick_length_seconds = tick_length_seconds
        self.width, self.depth = width, depth
        self.history_decay = history_decay
        self.anomaly_threshold = anomaly_threshold
        self.current_sketch = CountMinSketch(width, depth)
        self.total_sketch = CountMinSketch(width, depth)
        self.start_time = None
        self.current_tick = 0
        self.total_items_added = 0

    def _tick_for_timestamp(self, timestamp):
        timestamp = int(timestamp)
        if self.start_time is None:
            self.start_time = timestamp
        elapsed = max(0, timestamp - self.start_time)
        return max(1, elapsed // self.tick_length_seconds + 1)

    def score_edge(self, src, dst, timestamp):
        timestamp = int(timestamp)
        tick = self._tick_for_timestamp(timestamp)
        if tick > self.current_tick:
            if self.current_tick:
                self.total_sketch.decay(self.history_decay)
            self.current_sketch = CountMinSketch(self.width, self.depth)
            self.current_tick = tick

        key = f"{src}->{dst}"
        self.current_sketch.add(key)
        self.total_sketch.add(key)
        self.total_items_added += 1
        current = self.current_sketch.estimate(key)
        historical = self.total_sketch.estimate(key)
        expected = historical / self.current_tick
        score = 0.0 if historical <= 0 or current <= expected else (
            (current - expected) ** 2 * self.current_tick / historical
        )
        return {"src": str(src), "dst": str(dst), "timestamp": timestamp,
                "anomaly_score": round(float(score), 4),
                "is_alert": score >= self.anomaly_threshold}
