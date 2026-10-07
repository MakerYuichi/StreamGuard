"""
StreamGuard - DB Writer
Insert scored events and alerts into Postgres, matching the schema
in init-db/01_init.sql exactly.
"""

import json
from datetime import datetime, timezone

import psycopg2

from streamguard.consumer import config


_conn = None


def get_connection():
    global _conn

    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            dbname=config.POSTGRES_DB,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
        )

    return _conn


def write_score(scored_event: dict) -> None:
    """
    Insert a scored event into the scores table.

    Stores: src, dst, event_time, anomaly_score, is_alert, and label (if present).
    """
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            event_time = datetime.fromtimestamp(
                int(scored_event["timestamp"]),
                tz=timezone.utc,
            )

            cur.execute(
                """
                INSERT INTO scores (
                    src,
                    dst,
                    event_time,
                    anomaly_score,
                    is_alert,
                    label
                )
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    scored_event["src"],
                    scored_event["dst"],
                    event_time,
                    scored_event["anomaly_score"],
                    scored_event["is_alert"],
                    scored_event.get("label"),  # None if not present
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise


def write_alert(scored_event: dict, subgraph_nodes=None) -> dict:
    """
    Insert an alert into the alerts table and return the alert payload.
    """

    conn = get_connection()

    nodes = (
        subgraph_nodes
        if subgraph_nodes is not None
        else [
            scored_event["src"],
            scored_event["dst"],
        ]
    )

    try:
        with conn.cursor() as cur:
            event_time = datetime.fromtimestamp(
                int(scored_event["timestamp"]),
                tz=timezone.utc,
            )

            cur.execute(
                """
                INSERT INTO alerts (
                    src,
                    dst,
                    event_time,
                    score,
                    subgraph_nodes
                )
                VALUES (%s, %s, %s, %s, %s::jsonb)
                RETURNING alert_id;
                """,
                (
                    scored_event["src"],
                    scored_event["dst"],
                    event_time,
                    scored_event["anomaly_score"],
                    json.dumps(nodes),
                ),
            )

            alert_id = cur.fetchone()[0]

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return {
        "alert_id": str(alert_id),
        "src": scored_event["src"],
        "dst": scored_event["dst"],
        "timestamp": int(scored_event["timestamp"]),
        "score": scored_event["anomaly_score"],
        "subgraph_nodes": nodes,
    }