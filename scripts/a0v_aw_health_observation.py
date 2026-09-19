#!/usr/bin/env python3
"""Read-only AW lease observation; never invokes runtime or business operations."""
from __future__ import annotations

import argparse
import json

import a0v_aw_replacement_recovery as aw_replacement
import a0v_av_health_observation as health


health.replacement = aw_replacement.replacement
health.STATE = aw_replacement.replacement.STATE
health.OPERATION = "a0c9eed6-ab85-41eb-94e0-7eea26551b64"
health.INSTALLATION_LABEL = "aw"
health.INSTALLATION_ID = "f94b9425-9bc4-4369-8ae3-138c50c9ab81"
health.GENERATION = "a92f7bb2-3d90-4d88-9632-5fc9a70bd650"
health.ROUTE_REVISION = 120
health.GROUP_REVISION = 147
health.DEFINITION_REVISION = 76
health.OUTCOME = "AW_HEALTH_OBSERVATION_GREEN"


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
