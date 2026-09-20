#!/usr/bin/env python3
"""Read-only BJ lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bj_replacement_recovery as bj_replacement
import a0v_av_health_observation as health


health.replacement = bj_replacement.replacement
health.STATE = bj_replacement.replacement.STATE
health.OPERATION = "62ebeee2-aaef-4c49-acab-8d56ddb44ac0"
health.INSTALLATION_LABEL = "bj"
health.INSTALLATION_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"
health.GENERATION = "8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b"
health.ROUTE_REVISION = 156
health.GROUP_REVISION = 183
health.DEFINITION_REVISION = 109
health.OUTCOME = "BJ_HEALTH_OBSERVATION_GREEN"


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
