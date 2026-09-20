#!/usr/bin/env python3
"""Read-only BP lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_av_health_observation as health
import a0v_bp_replacement_recovery as bp_replacement


health.replacement = bp_replacement.replacement
health.STATE = bp_replacement.replacement.STATE
health.OPERATION = "4fd9f7d4-71ba-4451-8e60-1357f63b17ce"
health.INSTALLATION_LABEL = "bp"
health.INSTALLATION_ID = "17ba9792-9f24-42e4-9557-4d84547c7d97"
health.GENERATION = "4f1bddfa-74a0-4fcb-b25e-f363139eed83"
health.ROUTE_REVISION = 171
health.GROUP_REVISION = 198
health.DEFINITION_REVISION = 121
health.OUTCOME = "BP_HEALTH_OBSERVATION_GREEN"


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
