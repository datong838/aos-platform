#!/usr/bin/env python3
"""Read-only BN lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bn_replacement_recovery as bn_replacement
import a0v_av_health_observation as health


health.replacement = bn_replacement.replacement
health.STATE = bn_replacement.replacement.STATE
health.OPERATION = "4d4a686f-b32f-432d-a89d-dc1965cfa126"
health.INSTALLATION_LABEL = "bn"
health.INSTALLATION_ID = "d89bca67-4472-4b43-b0bd-ae8a2e0459f5"
health.GENERATION = "a43b3e64-7bb4-454c-822e-58bc13acbcaa"
health.ROUTE_REVISION = 165
health.GROUP_REVISION = 192
health.DEFINITION_REVISION = 118
health.OUTCOME = "BN_HEALTH_OBSERVATION_GREEN"


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
