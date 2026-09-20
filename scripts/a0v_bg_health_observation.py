#!/usr/bin/env python3
"""Read-only BG lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bg_replacement_recovery as bg_replacement
import a0v_av_health_observation as health


health.replacement = bg_replacement.replacement
health.STATE = bg_replacement.replacement.STATE
health.OPERATION = "9918bfc6-2b42-4472-a4dd-238c98f05684"
health.INSTALLATION_LABEL = "bg"
health.INSTALLATION_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"
health.GENERATION = "477c3f92-06f0-4dae-9445-ce6d09c3f462"
health.ROUTE_REVISION = 147
health.GROUP_REVISION = 174
health.DEFINITION_REVISION = 100
health.OUTCOME = "BG_HEALTH_OBSERVATION_GREEN"


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
