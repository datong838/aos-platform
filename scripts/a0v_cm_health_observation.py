#!/usr/bin/env python3
"""Read-only CM lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cm_replacement_recovery as cm_replacement


observer.health.replacement = cm_replacement.replacement
observer.health.STATE = cm_replacement.replacement.STATE
observer.health.OPERATION = "29cb2549-e72b-40df-bb46-7709a763da4c"
observer.health.INSTALLATION_LABEL = "cm"
observer.health.INSTALLATION_ID = "b52c8e1c-a343-4ef4-b106-38d859ba9677"
observer.health.GENERATION = "d3ec88cc-a05a-4895-bc27-c983a367a9a8"
observer.health.ROUTE_REVISION = 240
observer.health.GROUP_REVISION = 267
observer.health.DEFINITION_REVISION = 181
observer.health.OUTCOME = "CM_HEALTH_OBSERVATION_GREEN"
observer._CONNECTION_CACHED = False

snapshot = observer.snapshot
watch = observer.watch


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=int, required=True)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=int, default=960)
    args = parser.parse_args()
    result = watch(args.baseline, poll_seconds=args.poll_seconds,
                   timeout_seconds=args.timeout_seconds)
    output = observer.health.STATE / "health-observation-result.json"
    observer.health.replacement.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
