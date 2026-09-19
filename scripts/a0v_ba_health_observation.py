#!/usr/bin/env python3
"""Read-only BA lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_ba_replacement_recovery as ba_replacement
import a0v_av_health_observation as health


health.replacement = ba_replacement.replacement
health.STATE = ba_replacement.replacement.STATE
health.OPERATION = "82172075-d9ed-428f-8d5e-f201320aba7f"
health.INSTALLATION_LABEL = "ba"
health.INSTALLATION_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"
health.GENERATION = "197f5036-656a-4b58-a261-e93e2fffea18"
health.ROUTE_REVISION = 129
health.GROUP_REVISION = 156
health.DEFINITION_REVISION = 82
health.OUTCOME = "BA_HEALTH_OBSERVATION_GREEN"


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
