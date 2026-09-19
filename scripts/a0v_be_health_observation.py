#!/usr/bin/env python3
"""Read-only BE lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_be_replacement_recovery as be_replacement
import a0v_av_health_observation as health


health.replacement = be_replacement.replacement
health.STATE = be_replacement.replacement.STATE
health.OPERATION = "93f6b1cd-27bc-4614-8147-143cc95bfcfc"
health.INSTALLATION_LABEL = "be"
health.INSTALLATION_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"
health.GENERATION = "93349d9b-ad61-4919-9cbd-e1e9b02545bb"
health.ROUTE_REVISION = 141
health.GROUP_REVISION = 168
health.DEFINITION_REVISION = 94
health.OUTCOME = "BE_HEALTH_OBSERVATION_GREEN"


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
