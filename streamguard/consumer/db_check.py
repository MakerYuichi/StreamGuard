"""
StreamGuard - Phase 1 DB Connectivity Check
-----------------------------------------------
Purpose: prove Postgres and Redis actually work before anything
else is built on top of them. This is the "manually insert and
query a test row, don't assume it works" step from Phase 1.

Usage:
    python db_check.py
"""

import uuid
from datetime import datetime, timezone

import psycopg2
import redis

from streamguard.consumer import config
 

def check_postgres():
    print("[db_check] Connecting to Postgres ...")
    conn = psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )
    cur = conn.cursor()

    # --- Insert a real test row into `scores` ---
    cur.execute(
        """
        INSERT INTO scores (src, dst, event_time, anomaly_score, is_alert)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """,
        ("db_check_src", "db_check_dst", datetime.now(timezone.utc), 1.23, False),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    print(f"[db_check] Inserted test row into `scores` with id={new_id}")

    # --- Insert a real test row into `alerts` ---
    cur.execute(
        """
        INSERT INTO alerts (alert_id, src, dst, event_time, score, subgraph_nodes)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING alert_id;
        """,
        (str(uuid.uuid4()), "db_check_src", "db_check_dst",
         datetime.now(timezone.utc), 9.99, '["db_check_src", "db_check_dst"]'),
    )
    new_alert_id = cur.fetchone()[0]
    conn.commit()
    print(f"[db_check] Inserted test row into `alerts` with alert_id={new_alert_id}")

    # --- Read them back to prove round-trip works ---
    cur.execute("SELECT count(*) FROM scores;")
    print(f"[db_check] `scores` table now has {cur.fetchone()[0]} total rows")

    cur.execute("SELECT count(*) FROM alerts;")
    print(f"[db_check] `alerts` table now has {cur.fetchone()[0]} total rows")

    cur.close()
    conn.close()
    print("[db_check] Postgres: OK\n")


def check_redis():
    print("[db_check] Connecting to Redis ...")
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)

    r.set("db_check_key", "hello_streamguard")
    value = r.get("db_check_key")
    assert value == "hello_streamguard", "Redis round-trip failed!"
    print(f"[db_check] Redis set/get round-trip OK: got back '{value}'")

    r.delete("db_check_key")
    print("[db_check] Redis: OK\n")


if __name__ == "__main__":
    check_postgres()
    check_redis()
    print("[db_check] ALL CHECKS PASSED. Infrastructure is ready for Phase 2.")
