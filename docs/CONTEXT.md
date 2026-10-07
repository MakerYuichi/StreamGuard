# StreamGuard — Project Context

## What it is
StreamGuard is a real-time network-intrusion anomaly detector built on a streaming graph where nodes are IPs and edges are connections. It is a final-year capstone project.

## Repository layout
- `Backend-N/` — Python 3.12 backend
- `frontend/` — React + Vite frontend

## Detection pipeline
**Stage 1 — MIDAS-R scorer** (Bhatia et al., AAAI 2020): constant-memory, constant-time-per-event edge scoring using Count-Min Sketch. Every edge is scored; high-scoring edges are forwarded to Stage 2.

**Stage 2 — Subgraph confirmation**: for each flagged edge, pull the local k-hop neighbourhood, compute subgraph features, and run a trained supervised classifier to confirm or reject the alert. Every alert must carry a human-readable explanation of why it was flagged.

## Datasets
| Dataset | Role |
|---|---|
| CIC-IDS2017 | Primary (Source IP / Destination IP / Timestamp / flow features / Label) |
| UNSW-NB15 | Secondary |
| DARPA (existing files) | Legacy — regression tests only |
| NSL-KDD | **Not used** — no IPs or timestamps |

## Stack
Redpanda (Kafka-compatible), PostgreSQL + TimescaleDB, Redis, Python 3.12, WebSocket server, React + D3, Docker Compose.

## Research honesty rules
- Never claim something is implemented without a test or reproducible script that demonstrates it.
- Never invent or hardcode metrics — every number in docs must come from a script that writes to `results/`.
- We do **not** claim a new anomaly-detection algorithm. Contributions are: multi-feature scoring, a subgraph confirmation stage, an explainability layer, and the full streaming system with evaluation.
- Do **not** promise better accuracy than batch or GNN models. Honest target: near-batch accuracy with far lower memory and latency.
- Any deviation from the MIDAS paper must be documented in `docs/deviations.md`.

## Engineering rules
- Type hints on all Python code.
- Small, single-responsibility modules.
- pytest tests for all algorithm code.
- Configuration via environment variables — no hardcoded secrets.
- `.gitignore` must exclude secrets, data files, and `__pycache__`.
