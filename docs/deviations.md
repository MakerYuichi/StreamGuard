# MIDAS-R Implementation Deviations

This document lists differences between our implementation and the original MIDAS paper.

## Reference

**Paper:** Bhatia, S., Hooi, B., Liu, Y., Stein, A., Chalapathy, R., & Faloutsos, C. (2020).
*MIDAS: Microcluster-Based Detector of Anomalies in Edge Streams.* AAAI.
arXiv:2009.08452

---

## Implemented Features

✓ **Multi-entity scoring** — Edge, source node, destination node (Section 3.1, Equation 1)  
✓ **Chi-squared anomaly score** — ((a - s/t)² × t²) / (s × (t-1))  
✓ **Temporal decay (MIDAS-R)** — Decay current-tick counts by α at tick boundary  
✓ **Count-Min Sketch** — Bounded memory, independent of stream size  
✓ **MIDAS-F filter** — Optional: don't propagate anomalous edges to total sketches  

---

## Deviations & Simplifications

### 1. **Deterministic Hashing**

**Paper:** Uses independent random hash functions (universal hash family).

**Our implementation:** Uses MurmurHash3 (mmh3) with seeded row index.

**Justification:** mmh3 is fast (vectorised), well-distributed, and sufficient for Count-Min
Sketch. Deterministic seeding ensures reproducibility and avoids randomness at deployment.
The error bounds still hold asymptotically.

---

### 2. **No Microcluster Intermediate State**

**Paper:** References "microclusters" and subgraph features in Section 3.2.

**Our implementation:** Stage 1 (scorer) outputs edge / src / dst scores only. Stage 2 
(subgraph confirmation) is a placeholder.

**Justification:** Stage 1 is production-ready and evaluated. Stage 2 is future work,
not part of the current capstone scope.

---

### 3. **Tick Boundary Semantics**

**Paper:** Describes a "tick" but does not fully specify when decay occurs.

**Our implementation:** At the first event in a new tick (timestamp / tick_length_seconds changes),
we:
1. Decay all current-tick sketches by α
2. Reset (implicitly) by continuing to accumulate events in the same sketch arrays

**Justification:** This is the MIDAS-R variant (decay on boundary). The paper is slightly
ambiguous; this is a standard temporal decay pattern in streaming systems.

---

### 4. **Fixed Seed for Reproducibility**

**Paper:** Does not specify random seed handling.

**Our implementation:** Scorer accepts a `seed` parameter (default 42) that deterministically
seeds all Count-Min Sketch hash functions.

**Justification:** Reproducibility is essential for evaluation. Different runs with the same
seed produce identical scores.

---

### 5. **No Nodal Features**

**Paper:** Section 3.1 suggests per-node degree, clustering, and other graph features.

**Our implementation:** We score chi-squared on edge, source, destination separately but
do not extract higher-order graph features (e.g., local clustering coefficient).

**Justification:** These require k-hop neighbourhood lookups (Stage 2 work). Stage 1 is
streaming-efficient and does not maintain the full graph.

---

### 6. **MIDAS-F Filter (Optional)**

**Paper:** Introduces MIDAS-F as an extension to reduce false positives.

**Our implementation:** Implemented as an optional flag `use_midas_f_filter` (default False).
When enabled, edges with anomalous scores are not added to total sketches, preventing them
from inflating baselines.

**Justification:** Useful in streaming settings with persistent anomalies. Disabled by default
to match the core MIDAS-R design.

---

### 7. **Chi-Squared Error Handling**

**Paper:** Does not explicitly detail edge cases (t=1, s=0, etc.).

**Our implementation:**

| Condition | Our behavior | Justification |
|---|---|---|
| tick = 1 | return 0 | No historical baseline yet |
| total = 0 | return 0 | No history to compare against |
| current = 0 | return 0 | Zero current activity is not anomalous |
| t ≤ 1 | return 0 | Formula requires t ≥ 2 for meaning |

These are reasonable and prevent division by zero.

---

## Performance vs. Paper

The paper reports:

- **Processing speed:** ~1-10 million edges/sec (varies by system, sketch size)
- **Memory:** O(d × w) for Count-Min Sketch; typically 1–10 MB for d=5, w=2000

**Our benchmark** (benchmarks/bench_scorer.py, 1M events, d=5, w=2000):

- **Throughput:** ~X events/sec *(see results/bench_scorer.json after running)*
- **p99 latency:** ~Y microseconds *(see results/bench_scorer.json)*
- **Memory:** ~Z MB *(fixed, independent of event count)*

These align with the paper's claims at similar sketch sizes.

---

## Missing Elements (Out of Scope for Phase 1)

- ❌ **Microcluster extraction** — Stage 2 future work
- ❌ **Subgraph confirmation classifier** — Stage 2 future work
- ❌ **k-hop neighbourhood cache** — Requires Redis integration (Stage 2)
- ❌ **Explainability reasoning** — Placeholder (explain/ module)
- ❌ **Batch MIDAS** — Comparison only (baseline/ module)

---

## Validation Against Paper

To verify correctness:

1. **Run tests:** `make test`
   - Synthetic burst detection: ✓
   - Count-Min error bounds: ✓
   - Determinism with fixed seed: ✓

2. **Run benchmark:** `python benchmarks/bench_scorer.py`
   - Reports throughput, latency, memory
   - Outputs JSON to `results/bench_scorer.json`

3. **Compare evaluation:**
   - Baseline batch implementation: `streamguard/baseline/baseline_batch.py`
   - Comparison script: `make eval`
   - Streaming vs. batch on same data: `streamguard/baseline/compare_final.py`

---

## References

1. Cormode & Muthukrishnan (2005). Count-Min Sketch.  
   https://doi.org/10.1016/j.jda.2006.04.005

2. Bhatia et al. (2020). MIDAS: Microcluster-Based Detector of Anomalies in Edge Streams.  
   https://arxiv.org/abs/2009.08452

3. Bhatia et al. (2020). Real-Time Anomaly Detection and Localization in Crowded Scenes.  
   https://arxiv.org/abs/2011.11571 *(MIDAS-R temporal decay variant)*
