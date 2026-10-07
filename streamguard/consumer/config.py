"""
Thin re-export shim.

All settings now live in streamguard.config.  This file exists so that
code doing `from streamguard.consumer import config` or
`from streamguard.consumer.config import KAFKA_TOPIC` continues to work.
"""
from streamguard.config import (  # noqa: F401
    settings,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    REDIS_HOST,
    REDIS_PORT,
    WEBSOCKET_HOST,
    WEBSOCKET_PORT,
    ANOMALY_THRESHOLD,
)
