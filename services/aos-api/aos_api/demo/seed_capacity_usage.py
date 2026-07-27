"""Phase 2 seed · Capacity Usage — 30 days of daily usage.

Each day: total_requests / total_tokens / cost / peak_rpm.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.model_capacity import ensure_schema

log = get_logger("aos-api.demo.seed_capacity_usage")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_RANDOM = random.Random(42)  # deterministic


def seed_capacity_usage(*, days: int = 30) -> int:
    """Idempotently seed N days of capacity usage. Returns count."""
    ensure_schema()
    today = date.today()
    rows = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        total_requests = _RANDOM.randint(8000, 25000)
        total_tokens = total_requests * _RANDOM.randint(800, 2200)
        cost = round(total_tokens / 1_000_000 * _RANDOM.uniform(2.0, 5.0), 4)
        peak_rpm = _RANDOM.randint(300, 800)
        rows.append({
            "day": d.isoformat(),
            "totalRequests": total_requests,
            "totalTokens": total_tokens,
            "cost": cost,
            "peakRpm": peak_rpm,
        })

    with connect() as conn:
        conn.execute(
            "DELETE FROM capacity_usage WHERE org_id=%s AND project_id=%s",
            (_DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        for r in rows:
            conn.execute(
                """
                INSERT INTO capacity_usage (
                    id, day, total_requests, total_tokens, cost, peak_rpm,
                    org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (org_id, project_id, day) DO UPDATE SET
                    total_requests=EXCLUDED.total_requests,
                    total_tokens=EXCLUDED.total_tokens, cost=EXCLUDED.cost,
                    peak_rpm=EXCLUDED.peak_rpm
                """,
                (
                    f"cu-day-{r['day']}",
                    r["day"],
                    r["totalRequests"],
                    r["totalTokens"],
                    r["cost"],
                    r["peakRpm"],
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                ),
            )
        conn.commit()
    log.info("seed_capacity_usage_done days=%s", days)
    return days
