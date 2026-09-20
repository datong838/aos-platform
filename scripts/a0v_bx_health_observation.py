#!/usr/bin/env python3
"""Read-only BX lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

import a0v_av_health_observation as health
import a0v_bx_replacement_recovery as bx_replacement


health.replacement = bx_replacement.replacement
health.STATE = bx_replacement.replacement.STATE
health.OPERATION = "d3f509a2-0891-4348-b659-978694955721"
health.INSTALLATION_LABEL = "bx"
health.INSTALLATION_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"
health.GENERATION = "9beb5c99-aba7-4bec-9a10-4f98415aed2f"
health.ROUTE_REVISION = 195
health.GROUP_REVISION = 222
health.DEFINITION_REVISION = 136
health.OUTCOME = "BX_HEALTH_OBSERVATION_GREEN"
_CONNECTION_CACHED = False


def _cache_read_only_connection() -> None:
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
            raise ValueError("BX_HEALTH_DATABASE_NOT_ALLOWED")
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
