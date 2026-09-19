#!/usr/bin/env python3
"""Read-only BF lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bf_replacement_recovery as bf_replacement
import a0v_av_health_observation as health


health.replacement = bf_replacement.replacement
health.STATE = bf_replacement.replacement.STATE
health.OPERATION = "ccd5456d-cbc8-4ab7-a98b-8542a627b6b3"
health.INSTALLATION_LABEL = "bf"
health.INSTALLATION_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"
health.GENERATION = "e33e0a9e-7296-4374-9aa9-113f1ed79b5f"
health.ROUTE_REVISION = 144
health.GROUP_REVISION = 171
health.DEFINITION_REVISION = 97
health.OUTCOME = "BF_HEALTH_OBSERVATION_GREEN"


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
