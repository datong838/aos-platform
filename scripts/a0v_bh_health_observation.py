#!/usr/bin/env python3
"""Read-only BH lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bh_replacement_recovery as bh_replacement
import a0v_av_health_observation as health


health.replacement = bh_replacement.replacement
health.STATE = bh_replacement.replacement.STATE
health.OPERATION = "7c608516-30ad-4bb4-bef6-9e1b40a3b95f"
health.INSTALLATION_LABEL = "bh"
health.INSTALLATION_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"
health.GENERATION = "f6023b7c-ca6f-49ac-b9ff-4dcbca62745c"
health.ROUTE_REVISION = 150
health.GROUP_REVISION = 177
health.DEFINITION_REVISION = 103
health.OUTCOME = "BH_HEALTH_OBSERVATION_GREEN"


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
