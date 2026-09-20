#!/usr/bin/env python3
"""Read-only BL lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bl_replacement_recovery as bl_replacement
import a0v_av_health_observation as health


health.replacement = bl_replacement.replacement
health.STATE = bl_replacement.replacement.STATE
health.OPERATION = "319f1b2b-1cdf-49de-bc0c-b9779f018200"
health.INSTALLATION_LABEL = "bl"
health.INSTALLATION_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"
health.GENERATION = "116d12fc-93bc-4071-a973-fdc6830ea8b1"
health.ROUTE_REVISION = 162
health.GROUP_REVISION = 189
health.DEFINITION_REVISION = 115
health.OUTCOME = "BL_HEALTH_OBSERVATION_GREEN"


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
