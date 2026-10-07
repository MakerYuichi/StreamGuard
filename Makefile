# StreamGuard — top-level Makefile
# Run `make help` to see all targets.
#
# Assumes:
#   - Docker / Docker Compose available as `docker compose`
#   - Python 3.12+ venv activated (or `pip install -e .[dev]` already run)
#   - Node/npm available for the frontend
#
# All Python commands run from the repo root so `streamguard.*` imports resolve.

.PHONY: help infra-up infra-down test lint replay consumer frontend eval

# ── Default target ─────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "StreamGuard — available targets:"
	@echo ""
	@echo "  infra-up    Start Docker services (Redpanda, Postgres, Redis)"
	@echo "  infra-down  Stop and remove Docker services"
	@echo "  test        Run pytest test suite"
	@echo "  lint        Run ruff linter over the streamguard package and tests"
	@echo "  replay      Replay DARPA subset into Kafka (requires infra-up)"
	@echo "  consumer    Start the Phase-2 consumer (requires infra-up)"
	@echo "  frontend    Start the Vite dev server"
	@echo "  eval        Run the batch-vs-streaming comparison (requires infra-up + replay + consumer)"
	@echo ""

# ── Infrastructure ─────────────────────────────────────────────────────────────
infra-up:
	docker compose -f infra/docker-compose.yml up -d
	@echo "[infra] Waiting for services to be healthy..."
	@docker compose -f infra/docker-compose.yml ps

infra-down:
	docker compose -f infra/docker-compose.yml down

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

# ── Lint ───────────────────────────────────────────────────────────────────────
lint:
	ruff check streamguard/ tests/

# ── Backend services ───────────────────────────────────────────────────────────
replay:
	python -m streamguard.ingestion.darpa_replayer \
		data/darpa_subset.csv \
		--rate 200 \
		--no-header

consumer:
	python -m streamguard.consumer.consumer_v2

# ── Frontend ───────────────────────────────────────────────────────────────────
frontend:
	cd frontend && npm run dev

# ── Evaluation ─────────────────────────────────────────────────────────────────
eval:
	python -m streamguard.baseline.compare_final \
		data/darpa_subset.csv \
		--no-header \
		--ground-truth data/darpa_ground_truth_subset.csv \
		--window 10 \
		--zthresh 2.5
