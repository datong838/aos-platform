#!/usr/bin/env python3
"""Read-only AY lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_ay_replacement_recovery as ay_replacement
import a0v_av_health_observation as health


health.replacement = ay_replacement.replacement
health.STATE = ay_replacement.replacement.STATE
health.OPERATION = "fbd3b27a-d802-4ac3-8fd5-0549510e8455"
health.INSTALLATION_LABEL = "ay"
health.INSTALLATION_ID = "81df994f-23ce-4448-ac46-366aaee63924"
health.GENERATION = "a1069f60-46f5-41a8-bd18-61ed677eb3bd"
health.ROUTE_REVISION = 126
health.GROUP_REVISION = 153
health.DEFINITION_REVISION = 79
health.OUTCOME = "AY_HEALTH_OBSERVATION_GREEN"


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
