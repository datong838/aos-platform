#!/usr/bin/env python3
"""Read-only BI lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bi_replacement_recovery as bi_replacement
import a0v_av_health_observation as health


health.replacement = bi_replacement.replacement
health.STATE = bi_replacement.replacement.STATE
health.OPERATION = "4bdcc4a6-3cdc-4f65-aa34-4c08226bdcef"
health.INSTALLATION_LABEL = "bi"
health.INSTALLATION_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"
health.GENERATION = "6f527122-a4a5-4056-a4e6-ca888f4b64d7"
health.ROUTE_REVISION = 153
health.GROUP_REVISION = 180
health.DEFINITION_REVISION = 106
health.OUTCOME = "BI_HEALTH_OBSERVATION_GREEN"


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
