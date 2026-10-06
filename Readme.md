# StreamGuard — Project Status & Handoff

**For the team.** This document explains what the project is, what's actually
been built so far (Phases 1 & 2), and exactly what's left to do (Phases 3-5).
Read this before touching any code.

---

## 1. What this project actually is

StreamGuard is a real-time anomaly detection system for network traffic. It
watches a stream of `(source, destination, timestamp)` connection events —
the same shape as real network/IP traffic — and flags suspicious edges
(e.g. one host suddenly hammering another) **as they happen**, using an
algorithm that needs a *fixed, constant amount of memory* no matter how long
the stream runs.

This is NOT a machine learning project in the usual sense — there is no
trained model in the core engine. It's a **streaming systems + algorithms**
project. The only thing in this whole stack that is "trained" is the batch
comparison baseline, and even that is a simple naive statistical method, not
a neural net.

**The point of the project**, and the entire story for our demo/report, is:

> Our real-time engine (based on a peer-reviewed algorithm called MIDAS)
> detects attacks almost instantly, using constant memory. A naive
> batch-style approach (recompute stats every N seconds) is slower to react
> and still doesn't guarantee constant memory. We built both and measured
> the difference with real numbers.

### Papers we're implementing (cite these in the report)

- **Count-Min Sketch** — Cormode & Muthukrishnan, 2005. This is the memory
  structure. It lets us count how often an edge has occurred *approximately*,
  using fixed memory, instead of storing every edge we've ever seen.
- **MIDAS** — Bhatia, Hooi, Liu, Stein, Chalapathy, Faloutsos, AAAI 2020.
  This is the scoring formula on top of the sketch — it compares how often
  an edge is happening *right now* vs. how often it happens *on average*,
  and flags a big mismatch as anomalous.

We are NOT inventing the algorithm. We're implementing a real, citable paper
correctly, integrating it into a real pipeline, and comparing it against a
baseline — that integration + comparison is our actual contribution.

---

## 2. What's DONE — Phase 1

**Goal of Phase 1: prove all the infrastructure pipes work, using fake data.**

- `docker-compose.yml` sets up three services, all confirmed healthy:
  - `streamguard-postgres` (Postgres + TimescaleDB)
  - `streamguard-redis`
  - `streamguard-redpanda` (Kafka-compatible broker)
- Postgres schema created (`scores` and `alerts` tables) via `init-db/01_init.sql`
- Verified Postgres + Redis both work with real insert/read tests (`db_check.py`)
- Verified Kafka pipe end-to-end: a fake producer (`test_producer.py`) sends
  events, a consumer (`consumer_skeleton.py`) reads and prints them
- Frontend (React + D3) scaffolded with a force-directed graph rendering
  **hardcoded fake nodes/edges**, fully working, independent of the backend
- Naive batch baseline script (`baseline_batch.py`) built and tested
  successfully on a synthetic fake dataset with an injected "attack" —
  correctly caught the real attack edge (recall 1/1), with one false positive
  (precision 1/2), which is expected/healthy behavior for a naive baseline,
  not a bug

**Phase 1 is fully complete and verified working.**

---

## 3. What's DONE — Phase 2

**Goal of Phase 2: replace fake/placeholder logic with the real algorithm and real data, and wire everything together end-to-end.**

- **Real MIDAS algorithm implemented** (`algorithm/count_min_sketch.py` +
  `algorithm/midas_scorer.py`) — not a placeholder anymore. Implements the
  actual chi-squared scoring formula from the paper on top of a real
  Count-Min Sketch with decay.
- **Real DARPA dataset downloaded and verified:**
  - `data/darpa_processed.csv` — 4,554,344 rows, confirmed correct size
    (74MB) and correct line count (matches `darpa_shape.txt`)
  - `data/darpa_ground_truth.csv` — label file, confirmed label meaning:
    `0 = normal`, `1 = anomaly` (confirmed from the official MIDAS repo docs)
  - Confirmed this DARPA dataset is unusually attack-heavy (~60% of edges
    are labeled anomalous) — this is documented in the original paper, not
    a data problem on our end
- **Real ingestion built** (`ingestion/darpa_replayer.py`) — replays the
  real DARPA CSV into Kafka at a controlled rate, replacing the fake test
  producer
- **Real consumer pipeline built** (`consumer/consumer_v2.py`):
  - Consumes from Kafka
  - Scores every edge with the real MIDAS algorithm
  - Writes every scored event into Postgres `scores` table
  - Writes alerts (score above threshold) into Postgres `alerts` table
  - Broadcasts new alerts live over a WebSocket server
    (`consumer/websocket_server.py`)
- **Frontend wired to the live WebSocket feed** — no longer showing fake
  data; the graph now lights up in real time as real alerts arrive
- **Known bug fixed:** `db_writer.py` originally tried to insert a `label`
  column into `scores`, which doesn't exist in our schema (intentionally —
  the production scoring table has no ground truth, by design). Fixed to
  only insert the real production fields.
- **Comparison pipeline debugged and corrected today:**
  - Identified that streaming alerts were being counted at the *event*
    level (one anomalous edge can trigger many repeated alert rows as its
    score keeps climbing), while the batch baseline evaluates at the
    *unique edge* level — these weren't comparable as originally written
  - Built a shared `baseline/ground_truth.py` loader so both batch and
    streaming pull ground truth from the **same original DARPA label file**,
    never from Postgres (Postgres intentionally has no label column)
  - Built `baseline/compare_final.py` — the real apples-to-apples
    comparison: both batch and streaming are deduplicated to unique
    `(src, dst)` edges, scored against the same ground truth, side by side

**Phase 2 is functionally complete.** What's left in Phase 2's tail is purely
a performance/practicality issue, described below.

---

## 4. Known issue — currently blocking final numbers

Running `compare_final.py` (or `baseline_batch.py`) on the **full** 4.5M-row
DARPA file is too slow to finish in reasonable time. The baseline algorithm
re-scans all prior history before every 10-second window, which gets slower
as the stream progresses — this is an algorithmic cost of the *naive batch
baseline specifically*, not the real streaming engine (the real engine is
genuinely O(1) per event, which is itself a point worth highlighting in the
report).

**Immediate workaround (use this for now):** run on a matched subset of both
the data file and the ground truth file (same row range, same size) instead
of the full dataset:

```bash
cd data
head -n 50000 darpa_processed.csv > darpa_subset.csv
head -n 50000 darpa_ground_truth.csv > darpa_ground_truth_subset.csv
```

Then point both the replayer and the comparison script at the `_subset`
files instead of the full ones. Make sure whatever row count you use here
matches whatever `--limit` was used when the replayer sent data into Kafka,
so batch and streaming are evaluated on identical data.

---

## 5. What's NEXT — Phase 3, 4, 5

### Phase 3 — Finalize the evaluation (next immediate priority)

- [ ] Decide on a subset size (e.g. first 50k or 100k rows) that both the
      replayer and the comparison script will use consistently
- [ ] Re-run `consumer_v2.py` + `darpa_replayer.py` with that exact subset,
      end to end, so Postgres contains results from a known, matched dataset
- [ ] Run `compare_final.py` on that same subset and record the real
      precision/recall/edge-count numbers for both batch and streaming
- [ ] Sanity check the result against expectations: streaming should win
      decisively on **detection delay** (near-instant vs. waiting a full
      window); precision/recall may be close between the two or streaming
      may show more false positives due to MIDAS's sensitivity to bursts —
      if so, that's a legitimate, reportable tradeoff, not something to hide
      or "fix" by changing the algorithm
- [ ] (Optional, only if time allows) Replace the naive recompute-every-window
      baseline with an incrementally-updated version so it can handle the
      full dataset — not required for the demo, nice-to-have for the report

### Phase 4 — Full live demo rehearsal

- [ ] Run the entire pipeline live, start to finish, with everyone watching:
      `docker compose up` → `consumer_v2.py` → `darpa_replayer.py` →
      watch the frontend dashboard light up in real time
- [ ] Confirm the metrics panel on the frontend shows real numbers
      (events processed, alerts raised) — not placeholders
- [ ] Polish the dashboard only if time allows — labels, colors, make sure
      nothing visually breaks mid-demo. Do NOT add new features at this stage.
- [ ] Time the full demo run with a stopwatch — know exactly how long the
      replay takes so the live demo doesn't run long

### Phase 5 — Packaging & presentation

- [ ] Assemble the final comparison table/chart (batch vs. streaming:
      precision, recall, detection delay) as the centerpiece slide
- [ ] Write the short "Related Work" section citing both papers (Count-Min
      Sketch, MIDAS) and clearly stating what we reproduced vs. what we
      extended ourselves (the k-hop confirmation pass, if built; the
      head-to-head comparison study, which the original papers don't include)
- [ ] Decide who presents which part of the demo and rehearse the full
      sequence once, start to finish
- [ ] Freeze all code changes a few hours before presentation — only fix
      things that are actively broken, no new features

---

## 6. Quick reference — how to run everything right now

```bash
# 1. Infra (if not already running)
docker compose up -d
docker compose ps    # confirm all 3 healthy

# 2. Backend pipeline (two terminals)
cd consumer && python consumer_v2.py
cd ingestion && python darpa_replayer.py ../data/darpa_subset.csv --rate 200 --no-header

# 3. Frontend
cd frontend && npm run dev
# open http://localhost:5173

# 4. Evaluation (after the above has run for a while)
cd baseline
python compare_final.py ../data/darpa_subset.csv \
    --no-header \
    --ground-truth ../data/darpa_ground_truth_subset.csv \
    --window 10 --zthresh 2.5
```

---

## 7. Who to ask about what

| Area | Ask about |
|---|---|
| Algorithm correctness (MIDAS scoring, sketch) | Whoever built `algorithm/` |
| Kafka / data flow / replayer | Whoever built `ingestion/` |
| Postgres / Redis / WebSocket / consumer wiring | Whoever built `consumer/` |
| Dashboard / graph rendering | Whoever built `frontend/` |
| Baseline / evaluation / comparison numbers | Whoever built `baseline/` |

If you're picking up Phase 3 fresh, start by reading Section 4 (Known Issue)
and Section 6 (Quick Reference) — that's everything you need to get unblocked
and start producing real numbers.