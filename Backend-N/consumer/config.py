"""
StreamGuard - Shared Configuration
Matches the data/infra contract agreed on the whiteboard in Phase 0.
Every script imports from here instead of hardcoding values -
change a port/host ONCE here if you move to a shared machine.
"""

# ---- Kafka / Redpanda ----
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC = "raw-events"

# ---- Postgres ----
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5439
POSTGRES_DB = "streamguard"
POSTGRES_USER = "streamguard"
POSTGRES_PASSWORD = "streamguard"

# ---- Redis ----
REDIS_HOST = "localhost"
REDIS_PORT = 6379

# ---- WebSocket server (used in Phase 2) ----
WEBSOCKET_HOST = "0.0.0.0"
WEBSOCKET_PORT = 8080

# ---- Scoring threshold ----
# Provisional value agreed on the whiteboard - tune this once real
# scores are visible. Anything >= this is considered an alert.
ANOMALY_THRESHOLD = 3.0

# NOTE: If running on separate laptops instead of one shared machine,
# replace "localhost" above with the shared host machine's local network
# IP address (e.g. "192.168.1.42") in every script that imports this file.
