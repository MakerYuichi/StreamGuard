"""Standalone scorer smoke test: python -m algorithm.test_scorer"""
from algorithm.midas_scorer import MidasScorer


def main():
    scorer = MidasScorer(tick_length_seconds=5)
    base = 1_800_000_000
    for i in range(10):
        scorer.score_edge(f"192.168.1.{i}", f"10.0.0.{i}", base + i)
    results = [scorer.score_edge("attacker", "victim", base + 30 + i) for i in range(20)]
    assert all(set(result) == {"src", "dst", "timestamp", "anomaly_score", "is_alert"}
               for result in results)
    assert max(result["anomaly_score"] for result in results) > 0
    assert any(result["is_alert"] for result in results)
    print(f"scorer smoke check passed; burst peak={max(r['anomaly_score'] for r in results):.4f}")


if __name__ == "__main__":
    main()
