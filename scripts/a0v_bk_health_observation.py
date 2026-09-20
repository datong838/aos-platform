#!/usr/bin/env python3
"""Read-only BK lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_bk_replacement_recovery as bk_replacement
import a0v_av_health_observation as health


health.replacement = bk_replacement.replacement
health.STATE = bk_replacement.replacement.STATE
health.OPERATION = "ec59c319-ddeb-4022-97da-b232c0cf11fa"
health.INSTALLATION_LABEL = "bk"
health.INSTALLATION_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"
health.GENERATION = "9ea4ba9d-1ef8-45a6-9060-1e4f37c87038"
health.ROUTE_REVISION = 159
health.GROUP_REVISION = 186
health.DEFINITION_REVISION = 112
health.OUTCOME = "BK_HEALTH_OBSERVATION_GREEN"


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
