#!/usr/bin/env python3
"""Emit a deterministic, aggregate-only W2 dependency fact snapshot."""

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


PIPELINES = tuple(f"P{index:02d}" for index in range(1, 13))
OBJECT_TYPES = (
    "Shop",
    "Product",
    "ProductSku",
    "Category",
    "Order",
    "OrderLine",
    "Shipment",
    "CustomerLite",
    "Weapp",
    "SystemConfig",
    "ProductReview",
    "Payment",
)


def _dsn() -> str:
    configured = os.environ.get("AOS_DATABASE_URL")
    if configured:
        return configured
    repository_root = Path(__file__).resolve().parents[2]
    parser = configparser.ConfigParser()
    config_path = repository_root / "services" / "aos-api" / "alembic.ini"
    if not parser.read(config_path, encoding="utf-8"):
        raise RuntimeError("database configuration is unavailable")
    return parser.get("alembic", "sqlalchemy.url")


def _snapshot() -> dict[str, object]:
    with psycopg.connect(
        _dsn(),
        row_factory=dict_row,
        connect_timeout=5,
        options="-c statement_timeout=5000 -c lock_timeout=1000",
    ) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        latest = connection.execute(
            """
            WITH ranked AS (
              SELECT r.*,
                     row_number() OVER (
                       PARTITION BY schedule_id ORDER BY started_at DESC, id DESC
                     ) AS rn
                FROM meta_schedule_run r
               WHERE org_id=%s AND project_id=%s
            )
            SELECT s.pipeline_id, r.status, r.rows_written, r.error_code, r.started_at
              FROM meta_schedule s
              LEFT JOIN ranked r ON r.schedule_id=s.id AND r.rn=1
             WHERE s.org_id=%s AND s.project_id=%s
               AND s.id LIKE 'sch-P%%-qyh'
             ORDER BY s.pipeline_id
            """,
            ("org-org", "dev-project", "org-org", "dev-project"),
        ).fetchall()
        registered = connection.execute(
            """
            SELECT id FROM meta_pipeline
             WHERE org_id=%s AND project_id=%s
               AND substring(id from 1 for 3)=ANY(%s)
             ORDER BY id
            """,
            ("org-org", "dev-project", list(PIPELINES)),
        ).fetchall()
        source = connection.execute(
            """
            SELECT object_type, count(*) AS count
              FROM ecom_object
             WHERE org_id=%s AND workspace_id=%s AND object_type=ANY(%s)
             GROUP BY object_type ORDER BY object_type
            """,
            ("org-org", "dev-project", list(OBJECT_TYPES)),
        ).fetchall()
        projection = connection.execute(
            """
            SELECT object_type, count(*) AS count
              FROM obj_instance
             WHERE org_id=%s AND project_id=%s AND object_type=ANY(%s)
             GROUP BY object_type ORDER BY object_type
            """,
            ("org-org", "dev-project", list(OBJECT_TYPES)),
        ).fetchall()
        canary_source = connection.execute(
            """SELECT count(*) AS count FROM ecom_object
                 WHERE org_id=%s AND workspace_id=%s AND object_type=ANY(%s)""",
            ("dev-org", "dev-project", list(OBJECT_TYPES)),
        ).fetchone()
        canary_projection = connection.execute(
            """SELECT count(*) AS count FROM obj_instance
                 WHERE org_id=%s AND project_id=%s AND object_type=ANY(%s)""",
            ("dev-org", "dev-project", list(OBJECT_TYPES)),
        ).fetchone()
    return {
        "latestRuns": [
            {
                "pipelineId": row["pipeline_id"],
                "status": row["status"],
                "rowsWritten": row["rows_written"],
                "errorCode": row["error_code"],
                "startedAt": row["started_at"].isoformat() if row["started_at"] else None,
            }
            for row in latest
        ],
        "registeredPipelineIds": [row["id"] for row in registered],
        "sourceCounts": {row["object_type"]: row["count"] for row in source},
        "projectionCounts": {
            row["object_type"]: row["count"] for row in projection
        },
        "canary": {
            "sourceCount": canary_source["count"] if canary_source else None,
            "projectionCount": (
                canary_projection["count"] if canary_projection else None
            ),
        },
    }


def main() -> None:
    print(json.dumps(_snapshot(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
