#!/usr/bin/env python3
"""Read-only BB lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bb_replacement_recovery as bb_replacement
import a0v_av_health_observation as health


health.replacement = bb_replacement.replacement
health.STATE = bb_replacement.replacement.STATE
health.OPERATION = "c8577eb0-4670-4d37-a509-59dc22759562"
health.INSTALLATION_LABEL = "bb"
health.INSTALLATION_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"
health.GENERATION = "099c4d17-47fb-4c07-9ef1-c627ca7b4239"
health.ROUTE_REVISION = 132
health.GROUP_REVISION = 159
health.DEFINITION_REVISION = 85
health.OUTCOME = "BB_HEALTH_OBSERVATION_GREEN"


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
