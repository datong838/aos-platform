#!/usr/bin/env python3
"""Read-only CC lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cc_replacement_recovery as cc_replacement


observer.health.replacement = cc_replacement.replacement
observer.health.STATE = cc_replacement.replacement.STATE
observer.health.OPERATION = "d3bcdc60-c9b8-4afa-84d8-fe9441abafc1"
observer.health.INSTALLATION_LABEL = "cc"
observer.health.INSTALLATION_ID = "03942567-0f78-4530-b9dd-634bec59c780"
observer.health.GENERATION = "c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2"
observer.health.ROUTE_REVISION = 210
observer.health.GROUP_REVISION = 237
observer.health.DEFINITION_REVISION = 151
observer.health.OUTCOME = "CC_HEALTH_OBSERVATION_GREEN"
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
