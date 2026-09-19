#!/usr/bin/env python3
"""Read-only AZ lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_az_replacement_recovery as az_replacement
import a0v_av_health_observation as health


health.replacement = az_replacement.replacement
health.STATE = az_replacement.replacement.STATE
health.OPERATION = "e56b9d90-1396-4fa4-9c5c-3e7cc0f204b1"
health.INSTALLATION_LABEL = "az"
health.INSTALLATION_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"
health.GENERATION = "7b6befaa-2f92-4e62-85f9-0ca060ec4b90"
health.ROUTE_REVISION = 126
health.GROUP_REVISION = 153
health.DEFINITION_REVISION = 79
health.OUTCOME = "AZ_HEALTH_OBSERVATION_GREEN"


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
