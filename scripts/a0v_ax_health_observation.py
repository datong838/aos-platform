#!/usr/bin/env python3
"""Read-only AX lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_ax_replacement_recovery as ax_replacement
import a0v_av_health_observation as health


health.replacement = ax_replacement.replacement
health.STATE = ax_replacement.replacement.STATE
health.OPERATION = "0381b883-b37e-4559-900c-805265ab3891"
health.INSTALLATION_LABEL = "ax"
health.INSTALLATION_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"
health.GENERATION = "a14c911b-6796-4d22-a3b0-1817cf502de9"
health.ROUTE_REVISION = 123
health.GROUP_REVISION = 150
health.DEFINITION_REVISION = 76
health.OUTCOME = "AX_HEALTH_OBSERVATION_GREEN"


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
