#!/usr/bin/env python3
"""Read-only BQ lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_av_health_observation as health
import a0v_bq_replacement_recovery as bq_replacement


health.replacement = bq_replacement.replacement
health.STATE = bq_replacement.replacement.STATE
health.OPERATION = "8ede7aca-fcb4-47ba-9493-ea917c334fb1"
health.INSTALLATION_LABEL = "bq"
health.INSTALLATION_ID = "4faaf3b7-2d10-4961-99db-5bf52b7b8a63"
health.GENERATION = "b53ce5ac-169c-4d69-9780-58beb8ad736c"
health.ROUTE_REVISION = 174
health.GROUP_REVISION = 201
health.DEFINITION_REVISION = 124
health.OUTCOME = "BQ_HEALTH_OBSERVATION_GREEN"


def snapshot():
    return health.snapshot()


def watch(baseline: int, *, poll_seconds: int, timeout_seconds: int):
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
