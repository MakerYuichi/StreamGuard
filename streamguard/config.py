"""
StreamGuard — centralised typed configuration.

Every tunable value lives here.  Values are read from environment variables
(with safe defaults so the test suite runs without a .env file).  Import this
module everywhere instead of the old streamguard/consumer/config.py.

Usage:
    from streamguard.config import settings
    print(settings.kafka_bootstrap_servers)

Loading .env automatically (dev only):
    The module calls load_dotenv() at import time so a .env file in the repo
    root is picked up without any extra setup step.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load .env from the repo root (no-op if the file doesn't exist or
# if the variables are already set in the real environment).
load_dotenv()


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


@dataclass(frozen=True)
class Settings:
    # ── Kafka / Redpanda ───────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = field(
        default_factory=lambda: _env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    kafka_topic: str = field(
        default_factory=lambda: _env("KAFKA_TOPIC", "raw-events")
    )

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    postgres_host: str = field(
        default_factory=lambda: _env("POSTGRES_HOST", "localhost")
    )
    postgres_port: int = field(
        default_factory=lambda: _int("POSTGRES_PORT", 5439)
    )
    postgres_db: str = field(
        default_factory=lambda: _env("POSTGRES_DB", "streamguard")
    )
    postgres_user: str = field(
        default_factory=lambda: _env("POSTGRES_USER", "streamguard")
    )
    postgres_password: str = field(
        default_factory=lambda: _env("POSTGRES_PASSWORD", "streamguard")
    )

    # ── Redis ──────────────────────────────────────────────────────────────────
    redis_host: str = field(
        default_factory=lambda: _env("REDIS_HOST", "localhost")
    )
    redis_port: int = field(
        default_factory=lambda: _int("REDIS_PORT", 6379)
    )

    # ── WebSocket server ───────────────────────────────────────────────────────
    websocket_host: str = field(
        default_factory=lambda: _env("WEBSOCKET_HOST", "0.0.0.0")
    )
    websocket_port: int = field(
        default_factory=lambda: _int("WEBSOCKET_PORT", 8080)
    )

    # ── MIDAS scorer ───────────────────────────────────────────────────────────
    anomaly_threshold: float = field(
        default_factory=lambda: _float("ANOMALY_THRESHOLD", 3.0)
    )
    tick_length_seconds: int = field(
        default_factory=lambda: _int("TICK_LENGTH_SECONDS", 10)
    )
    sketch_width: int = field(
        default_factory=lambda: _int("SKETCH_WIDTH", 2000)
    )
    sketch_depth: int = field(
        default_factory=lambda: _int("SKETCH_DEPTH", 5)
    )
    history_decay: float = field(
        default_factory=lambda: _float("HISTORY_DECAY", 0.98)
    )

    # ── Convenience: psycopg2 DSN dict ────────────────────────────────────────
    def pg_dsn(self) -> dict[str, str | int]:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password,
        }


# Module-level singleton — import this everywhere.
settings = Settings()


# ── Legacy shim ───────────────────────────────────────────────────────────────
# The old consumer/config.py exported bare uppercase names.
# These module-level aliases let any code that still does
#   from streamguard.consumer.config import KAFKA_TOPIC
# keep working without changes during the transition.
KAFKA_BOOTSTRAP_SERVERS = settings.kafka_bootstrap_servers
KAFKA_TOPIC             = settings.kafka_topic
POSTGRES_HOST           = settings.postgres_host
POSTGRES_PORT           = settings.postgres_port
POSTGRES_DB             = settings.postgres_db
POSTGRES_USER           = settings.postgres_user
POSTGRES_PASSWORD       = settings.postgres_password
REDIS_HOST              = settings.redis_host
REDIS_PORT              = settings.redis_port
WEBSOCKET_HOST          = settings.websocket_host
WEBSOCKET_PORT          = settings.websocket_port
ANOMALY_THRESHOLD       = settings.anomaly_threshold
