#!/usr/bin/env python3
"""Read-only BT lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

import a0v_av_health_observation as health
import a0v_bt_replacement_recovery as bt_replacement


health.replacement = bt_replacement.replacement
health.STATE = bt_replacement.replacement.STATE
health.OPERATION = "db62985a-616d-4dca-9a1b-44234d5e47f0"
health.INSTALLATION_LABEL = "bt"
health.INSTALLATION_ID = "b05b7f06-67a0-4ea1-bc7c-1ba2108653d5"
health.GENERATION = "2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58"
health.ROUTE_REVISION = 183
health.GROUP_REVISION = 210
health.DEFINITION_REVISION = 127
health.OUTCOME = "BT_HEALTH_OBSERVATION_GREEN"
_CONNECTION_CACHED = False


def _cache_read_only_connection() -> None:
    """Resolve the fixed container endpoint once; sampling must not repeat inspect calls."""
    global _CONNECTION_CACHED
    if _CONNECTION_CACHED:
        return
    import a0v_formal_text_model_renewal as renewal
    original = renewal.database_connect
    with original("aos_meta_head")() as conn:
        parameters = conn.info.get_parameters()
        parameters["password"] = conn.info.password
    parameters["dbname"] = "aos_meta_head"

    @contextmanager
    def connect():
        with psycopg.connect(**parameters, row_factory=dict_row) as conn:
            conn.read_only = True
            conn.isolation_level = IsolationLevel.REPEATABLE_READ
            yield conn

    def cached(database_name: str):
        if database_name != "aos_meta_head":
            raise ValueError("BT_HEALTH_DATABASE_NOT_ALLOWED")
        return connect

    renewal.database_connect = cached
    health.database_connect = cached
    _CONNECTION_CACHED = True


def snapshot():
    _cache_read_only_connection()
    return health.snapshot()


def watch(baseline: int, *, poll_seconds: int, timeout_seconds: int):
    _cache_read_only_connection()
    return health.watch(baseline, poll_seconds=poll_seconds, timeout_seconds=timeout_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=int, required=True)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=int, default=960)
    args = parser.parse_args()
    result = watch(args.baseline, poll_seconds=args.poll_seconds,
                   timeout_seconds=args.timeout_seconds)
    output = health.STATE / "health-observation-result.json"
    health.replacement.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
