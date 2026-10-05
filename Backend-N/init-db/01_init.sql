-- StreamGuard - Phase 1 Database Schema
-- Auto-runs when the Postgres container first starts (via docker-entrypoint-initdb.d)
-- Matches the data contract agreed on the whiteboard:
--   Scored Event: src, dst, timestamp, anomaly_score, is_alert
--   Alert:        alert_id, src, dst, timestamp, score, subgraph_nodes

-- Enable TimescaleDB extension (safe to run even if already enabled)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- Table 1: scores
-- Every single scored edge gets a row here, alert or not.
-- This is the time-series table used later for throughput/latency
-- graphs and for the accuracy evaluation (Role 5's work).
-- ============================================================
CREATE TABLE IF NOT EXISTS scores (
    id              BIGSERIAL,
    src             TEXT        NOT NULL,
    dst             TEXT        NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL,   -- converted from the incoming unix timestamp
    anomaly_score   DOUBLE PRECISION NOT NULL,
    is_alert        BOOLEAN     NOT NULL DEFAULT FALSE,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),  -- when OUR system processed it (for latency measurement)
    PRIMARY KEY (id, event_time)
);

-- Turn it into a TimescaleDB hypertable partitioned by event_time.
-- This is what gives fast time-range queries even with millions of rows.
-- If this line fails (e.g., TimescaleDB extension not available), just
-- comment it out -- the plain table still works fine for a 2-day sprint.
SELECT create_hypertable('scores', 'event_time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_scores_is_alert ON scores (is_alert) WHERE is_alert = TRUE;
CREATE INDEX IF NOT EXISTS idx_scores_src_dst ON scores (src, dst);

-- ============================================================
-- Table 2: alerts
-- Only confirmed/flagged anomalies land here. This is what gets
-- pushed over the WebSocket to the frontend.
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    alert_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    src             TEXT        NOT NULL,
    dst             TEXT        NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL,
    score           DOUBLE PRECISION NOT NULL,
    subgraph_nodes  JSONB       NOT NULL DEFAULT '[]'::jsonb,  -- list of node IDs; [] if k-hop pass not built yet
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_event_time ON alerts (event_time DESC);

-- pgcrypto needed for gen_random_uuid() above on some Postgres builds
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- Sanity check row (safe to delete later) -- proves the schema works
-- ============================================================
INSERT INTO scores (src, dst, event_time, anomaly_score, is_alert)
VALUES ('test_src', 'test_dst', now(), 0.0, FALSE);
