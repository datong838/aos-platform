#!/usr/bin/env python3
"""Read-only BO lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bo_replacement_recovery as bo_replacement
import a0v_av_health_observation as health


health.replacement = bo_replacement.replacement
health.STATE = bo_replacement.replacement.STATE
health.OPERATION = "878d3c80-038a-43f7-b011-61ceb8ad0ae0"
health.INSTALLATION_LABEL = "bo"
health.INSTALLATION_ID = "307399a0-21bb-4d55-95b2-8b0fee238913"
health.GENERATION = "030bf59c-c998-4ee6-aedb-11d8d7d5831a"
health.ROUTE_REVISION = 168
health.GROUP_REVISION = 195
health.DEFINITION_REVISION = 118
health.OUTCOME = "BO_HEALTH_OBSERVATION_GREEN"


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
