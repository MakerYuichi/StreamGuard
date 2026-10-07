"""
MIDAS-R Scorer Benchmark

Measures:
- Throughput (events/sec)
- Per-event latency (p50, p95, p99)
- Memory overhead
- Error bounds

Outputs JSON report to results/bench_scorer.json.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamguard.algorithm.midas_scorer import MidasScorer


def benchmark_throughput_and_latency(
    num_events: int = 1_000_000,
    burst_start: int = 500_000,
    burst_duration: int = 10_000,
) -> dict:
    """
    Benchmark scorer throughput and latency.

    Args:
        num_events: Total events to process.
        burst_start: Event index where burst begins.
        burst_duration: How many events in the burst.

    Returns:
        Dict with throughput, latencies, and memory stats.
    """
    scorer = MidasScorer(
        width=2000,
        depth=5,
        tick_length_seconds=10,
        alpha=0.98,
        anomaly_threshold=3.0,
        seed=42,
    )

    base_ts = 1_700_000_000
    latencies = []
    alert_count = 0
    burst_alerts = 0

    print(f"Processing {num_events:,} events...")

    start_time = time.perf_counter()

    for i in range(num_events):
        # Generate event
        if burst_start <= i < burst_start + burst_duration:
            # Burst: attacker → victim
            src, dst = "192.168.1.255", "10.0.0.255"
        else:
            # Normal: diverse traffic
            src = f"192.168.1.{(i // 100) % 100}"
            dst = f"10.0.0.{(i // 100) % 100}"

        ts = base_ts + i // 100  # 100 events per second

        # Time the scoring
        t0 = time.perf_counter()
        result = scorer.score_edge(src, dst, ts)
        t1 = time.perf_counter()

        latencies.append((t1 - t0) * 1_000_000)  # Convert to microseconds

        if result.is_alert:
            alert_count += 1
            if burst_start <= i < burst_start + burst_duration:
                burst_alerts += 1

        if (i + 1) % 100_000 == 0:
            print(f"  {i + 1:,} events processed...")

    total_time = time.perf_counter() - start_time

    # Compute statistics
    latencies_array = np.array(latencies)
    throughput = num_events / total_time

    report = {
        "benchmark": "MIDAS-R Scorer",
        "num_events": num_events,
        "total_time_seconds": round(total_time, 2),
        "throughput_events_per_sec": round(throughput, 0),
        "latency_microseconds": {
            "p50": round(float(np.percentile(latencies_array, 50)), 2),
            "p95": round(float(np.percentile(latencies_array, 95)), 2),
            "p99": round(float(np.percentile(latencies_array, 99)), 2),
            "min": round(float(np.min(latencies_array)), 2),
            "max": round(float(np.max(latencies_array)), 2),
        },
        "memory": {
            "sketch_bytes": scorer.memory_bytes(),
            "sketch_mb": round(scorer.memory_bytes() / (1024 * 1024), 2),
        },
        "alerts": {
            "total": alert_count,
            "in_burst": burst_alerts,
            "burst_detection_rate": (
                round(100.0 * burst_alerts / burst_duration, 1)
                if burst_duration > 0
                else 0
            ),
        },
        "error_bounds": {
            "epsilon": round(float(scorer.error_bound()[0]), 6),
            "delta": round(float(scorer.error_bound()[1]), 6),
        },
        "configuration": scorer.to_dict(),
    }

    return report


def main() -> None:
    """Run benchmark and save report."""
    results_dir = Path(__file__).resolve().parents[1] / "results"
    results_dir.mkdir(exist_ok=True)

    print("═" * 70)
    print("MIDAS-R Scorer Benchmark")
    print("═" * 70)
    print()

    report = benchmark_throughput_and_latency()

    # Print to console
    print()
    print("═" * 70)
    print("RESULTS")
    print("═" * 70)
    print()
    print(f"Throughput:        {report['throughput_events_per_sec']:,.0f} events/sec")
    print(f"Total time:        {report['total_time_seconds']:.2f} seconds")
    print()
    print("Latency (microseconds):")
    print(f"  p50:             {report['latency_microseconds']['p50']:.2f}")
    print(f"  p95:             {report['latency_microseconds']['p95']:.2f}")
    print(f"  p99:             {report['latency_microseconds']['p99']:.2f}")
    print(f"  min:             {report['latency_microseconds']['min']:.2f}")
    print(f"  max:             {report['latency_microseconds']['max']:.2f}")
    print()
    print(f"Memory:            {report['memory']['sketch_mb']:.2f} MB "
          f"({report['memory']['sketch_bytes']:,} bytes)")
    print()
    print("Anomaly Detection:")
    print(f"  Total alerts:    {report['alerts']['total']}")
    print(f"  Burst alerts:    {report['alerts']['in_burst']}")
    print(f"  Burst detection: {report['alerts']['burst_detection_rate']:.1f}%")
    print()
    print("Error Bounds (Count-Min Sketch):")
    print(f"  ε (epsilon):     {report['error_bounds']['epsilon']:.6f}")
    print(f"  δ (delta):       {report['error_bounds']['delta']:.6f}")
    print()

    # Save to JSON
    output_path = results_dir / "bench_scorer.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
