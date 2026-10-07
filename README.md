# StreamGuard — Real-Time Network Anomaly Detection

A streaming anomaly detector for network intrusions using a bounded-memory, constant-time-per-event MIDAS-inspired scorer (Stage 1) and a supervised subgraph confirmation stage (Stage 2, future work).

**Project status:** Phase 1 and Phase 2 infrastructure complete. Evaluation on synthetic DARPA data complete. Ready for CIC-IDS2017 integration.

---

## Quick Start

### 1. Prerequisites

- **Docker & Docker Compose** — for Kafka, Postgres, Redis
- **Python 3.12+** — with pip
- **Node 18+** — for the frontend

### 2. Start infrastructure

```bash
make infra-up
```

This starts Redpanda (Kafka-compatible), PostgreSQL with TimescaleDB, and Redis. Wait for all services to show healthy:

```bash
docker compose -f infra/docker-compose.yml ps
```

### 3. Install Python dependencies

```bash
pip install -e .
```

### 4. Start the consumer

In one terminal:

```bash
make consumer
```

### 5. Start the frontend

In another terminal:

```bash
make frontend
```

Then open **http://localhost:5173**.

### 6. Replay data

In a third terminal:

```bash
make replay
```

The dashboard will show live alerts as the DARPA subset replays.

---

## Project Structure

```
streamguard/
├── algorithm/          # Count-Min Sketch, MIDAS-R scorer
├── consumer/           # Kafka consumer, DB writes, WebSocket
├── ingestion/          # DARPA replayer and Kafka producer
├── baseline/           # Batch baseline and comparison scripts
├── stage2/             # [Placeholder] Subgraph confirmation
├── models/             # [Placeholder] Trained classifiers
└── explain/            # [Placeholder] Explainability layer

infra/
├── docker-compose.yml  # Services: Redpanda, Postgres, Redis
├── init-db/            # Base schema (idempotent)
└── migrations/         # Future schema changes (idempotent)

data/
├── README.md           # Where to download CIC-IDS2017, UNSW-NB15
├── darpa_*.csv         # Legacy regression test data
└── fake_traffic.csv    # Synthetic burst for testing

tests/
├── test_scorer.py      # Algorithm smoke tests
└── fixtures/           # Small CSVs for rapid unit tests

frontend/
├── src/                # React + D3 dashboard
├── .env.example        # WebSocket URL (Vite env)
└── package.json

docs/
├── CONTEXT.md          # Project context (for developers)
└── deviations.md       # [Future] How we differ from MIDAS paper

.env.example            # Python backend settings
Makefile                # Build, test, run targets
pyproject.toml          # Dependencies and build config
```

---

## Available Make Targets

```bash
make help          # Show all targets
make infra-up      # Start Docker services
make infra-down    # Stop Docker services
make test          # Run pytest
make lint          # Run ruff linter
make replay        # Replay DARPA subset to Kafka
make consumer      # Start the Phase-2 consumer
make frontend      # Start Vite dev server
make eval          # Run batch-vs-streaming comparison
```

---

## Configuration

All backend settings are environment variables, read from `.env` if present. Copy the example and edit as needed:

```bash
cp .env.example .env
```

**Key settings:**
- `KAFKA_BOOTSTRAP_SERVERS` — Redpanda address
- `POSTGRES_*` — Database credentials
- `ANOMALY_THRESHOLD` — Score threshold for alerts
- `TICK_LENGTH_SECONDS`, `SKETCH_WIDTH`, `SKETCH_DEPTH`, `HISTORY_DECAY` — MIDAS parameters

For the frontend:

```bash
cp frontend/.env.example frontend/.env.local
# Edit VITE_WS_URL to point to your WebSocket server
```

---

## Architecture

### Stage 1: MIDAS-Inspired Streaming Scorer

Every edge `(src, dst)` is scored in real-time using a Count-Min Sketch:

1. Current-tick sketch counts recent activity on the edge.
2. Total sketch (with decay) estimates historical frequency.
3. Score = (current - expected)² × tick / historical.
4. If score ≥ threshold, flag as alert.

**Memory:** O(sketch_width × sketch_depth) — constant, independent of stream size.  
**Time per event:** O(sketch_depth) — typically 5 hashes.

### Stage 2: Subgraph Confirmation (Future)

For Stage 1 alerts, pull the k-hop neighbourhood around `(src, dst)` and extract subgraph features (degree, clustering, flow patterns). Train a supervised classifier (e.g., isolation forest) to confirm or reject the alert.

### Storage & Visualization

- **PostgreSQL/TimescaleDB** stores all scores (with labels) and alerts.
- **WebSocket** broadcasts alerts to the React dashboard in real time.
- **Redis** holds k-hop adjacencies (future k-hop confirmation stage).

---

## Datasets

### Primary: CIC-IDS2017

[Download](https://www.unb.ca/cic/datasets/ids-2017.html) the pre-processed CSVs.

Required columns: `Source IP`, `Destination IP`, `Timestamp`, flow features, `Label`.  
Place in `data/cic-ids2017/`.

### Secondary: UNSW-NB15

[Download](https://research.unsw.edu.au/projects/unsw-nb15-dataset) the CSV files.  
Place in `data/unsw-nb15/`.

### Legacy: DARPA 1998

The existing `data/darpa_*.csv` files are **regression tests only** and should not be used for primary evaluation (they are synthetic modifications of the original dataset, which has no IP addresses in raw form).

---

## Evaluation

### Test Suite

```bash
make test
```

Runs pytest on `tests/` (algorithm smoke tests, fixture validation).

### Batch vs. Streaming Comparison

```bash
make eval
```

Runs the baseline (10-second window, z-score threshold) against the streaming MIDAS scorer on the same DARPA subset. Outputs precision, recall, and detection delay.

---

## Known Limitations

### Legacy DARPA Metrics

The metrics reported in `README.md` (prior to October 2026 restructuring) were from a small, synthetic DARPA subset:

- **Rows:** 350,001–450,000 (100,000 events, ~1,000 unique edges)
- **Threshold:** Highly sensitive (3.0) — many false positives
- **Recall:** 1.0 at threshold 3 but precision only 0.188
- **AUC:** 0.968 (threshold-independent)

These results **cannot be generalized** to production networks or real-world datasets (CIC-IDS2017, UNSW-NB15). They serve as proof-of-concept and regression tests only.

### Current Implementation Gaps

1. **Stage 2 unimplemented** — Subgraph confirmation is a placeholder; only Stage 1 (MIDAS scorer) is active.
2. **No explainability** — Alerts show score but not reasoning (why was this edge flagged?).
3. **Threshold tuning** — Current threshold (3.0) is exploratory; production use requires threshold sweep on labeled data.
4. **Not a new algorithm** — The scorer is MIDAS-inspired, not a novel contribution. The contribution is the end-to-end streaming system, evaluation workflow, and integration.
5. **Streaming vs. batch accuracy** — We do **not** claim better accuracy than batch or GNN models. The goal is comparable accuracy with far lower memory and latency.

### Test Data Limitations

- DARPA data is legacy (synthetic, no raw IPs); use only for regression.
- Small fixtures (1,000 rows) in `tests/fixtures/` are not representative of production scale.
- No production traffic baseline; tuning will require real customer data.

---

## Deployment

### Docker

The system is fully containerised. Build an image:

```dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["python", "-m", "streamguard.consumer.consumer_v2"]
```

### Environment

Set environment variables for your deployment:
- Kafka bootstrap server (if not localhost:9092)
- Postgres credentials
- WebSocket host/port
- MIDAS parameters (tick length, sketch size, decay, threshold)

All settings are documented in `.env.example`.

---

## Contributing

1. Follow PEP 8 + use type hints.
2. Add tests for new algorithm code.
3. Run `make lint` and `make test` before pushing.
4. Update `docs/` if you change a design decision or add a feature.

---

## References

- Cormode, G., & Muthukrishnan, S. (2005). *Count-Min Sketch*.
- Bhatia, S., Hooi, B., Liu, Y., Stein, A., Chalapathy, R., & Faloutsos, C. (2020). *MIDAS: Microcluster-Based Detector of Anomalies in Edge Streams.* AAAI.
- Hamilton, W., Ying, Z., & Leskovec, J. (2017). *Inductive Representation Learning on Large Graphs.* NeurIPS.

---

## License

[Add your license here]
