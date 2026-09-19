#!/usr/bin/env python3
"""Read-only BD lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bd_replacement_recovery as bd_replacement
import a0v_av_health_observation as health


health.replacement = bd_replacement.replacement
health.STATE = bd_replacement.replacement.STATE
health.OPERATION = "64e80251-affc-4155-82ae-faafc9cdcaa1"
health.INSTALLATION_LABEL = "bd"
health.INSTALLATION_ID = "c2d6ef97-30ec-4980-9421-54a899607853"
health.GENERATION = "f5e01f1d-e6c5-425a-9145-6f7a82ec65e5"
health.ROUTE_REVISION = 138
health.GROUP_REVISION = 165
health.DEFINITION_REVISION = 91
health.OUTCOME = "BD_HEALTH_OBSERVATION_GREEN"


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
