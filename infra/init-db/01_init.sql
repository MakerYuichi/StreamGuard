-- StreamGuard - Phase 1 Database Schema
-- Auto-runs when the Postgres container first starts (via docker-entrypoint-initdb.d)
-- All statements are idempotent: safe to re-run.

-- Enable TimescaleDB extension (safe to run even if already enabled)
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- Table 1: scores
-- Every single scored edge gets a row here, alert or not.
-- Stores: src, dst, event_time, anomaly_score, is_alert, label (if available)
-- ============================================================
CREATE TABLE IF NOT EXISTS scores (
    id              BIGSERIAL,
    src             TEXT        NOT NULL,
    dst             TEXT        NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL,
    anomaly_score   DOUBLE PRECISION NOT NULL,
    is_alert        BOOLEAN     NOT NULL DEFAULT FALSE,
    label           SMALLINT    CHECK (label IN (0, 1)),
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, event_time)
);

-- Ensure label column exists (for migration from old schema)
ALTER TABLE scores ADD COLUMN IF NOT EXISTS label SMALLINT CHECK (label IN (0, 1));

-- TimescaleDB hypertable (idempotent)
SELECT create_hypertable('scores', 'event_time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_scores_is_alert ON scores (is_alert) WHERE is_alert = TRUE;
CREATE INDEX IF NOT EXISTS idx_scores_src_dst ON scores (src, dst);

-- ============================================================
-- Table 2: alerts
-- Only flagged anomalies land here. Pushed over WebSocket to frontend.
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    alert_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    src             TEXT        NOT NULL,
    dst             TEXT        NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL,
    score           DOUBLE PRECISION NOT NULL,
    subgraph_nodes  JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_event_time ON alerts (event_time DESC);

-- ============================================================
-- Sanity check row (safe to delete) — proves the schema works
-- ============================================================
INSERT INTO scores (src, dst, event_time, anomaly_score, is_alert)
VALUES ('test_src', 'test_dst', now(), 0.0, FALSE)
ON CONFLICT DO NOTHING;
