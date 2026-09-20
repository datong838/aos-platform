#!/usr/bin/env python3
"""Read-only BU lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

import a0v_av_health_observation as health
import a0v_bu_replacement_recovery as bu_replacement


health.replacement = bu_replacement.replacement
health.STATE = bu_replacement.replacement.STATE
health.OPERATION = "a36f4a07-d71b-4f8b-bf12-5569a5c08fba"
health.INSTALLATION_LABEL = "bu"
health.INSTALLATION_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"
health.GENERATION = "cb8ace71-ba8d-4e08-816b-8d6bbc0f0281"
health.ROUTE_REVISION = 186
health.GROUP_REVISION = 213
health.DEFINITION_REVISION = 127
health.OUTCOME = "BU_HEALTH_OBSERVATION_GREEN"
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
            raise ValueError("BU_HEALTH_DATABASE_NOT_ALLOWED")
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
