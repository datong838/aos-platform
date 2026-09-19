#!/usr/bin/env python3
"""Read-only BC lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bc_replacement_recovery as bc_replacement
import a0v_av_health_observation as health


health.replacement = bc_replacement.replacement
health.STATE = bc_replacement.replacement.STATE
health.OPERATION = "1af66cab-bc7b-4499-97db-194c52181e0d"
health.INSTALLATION_LABEL = "bc"
health.INSTALLATION_ID = "3b895c30-34ca-4710-b978-02645d49c83a"
health.GENERATION = "31776dcd-e28f-4b6d-ae45-75fb0ab5a505"
health.ROUTE_REVISION = 135
health.GROUP_REVISION = 162
health.DEFINITION_REVISION = 88
health.OUTCOME = "BC_HEALTH_OBSERVATION_GREEN"


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
