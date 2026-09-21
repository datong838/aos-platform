#!/usr/bin/env python3
"""Read-only CX lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cx_replacement_recovery as cx_replacement


observer.health.replacement = cx_replacement.replacement
observer.health.STATE = cx_replacement.replacement.STATE
observer.health.OPERATION = "03652e8e-fb4d-4400-be26-3512ff374418"
observer.health.INSTALLATION_LABEL = "cx"
observer.health.INSTALLATION_ID = "2e374e12-7523-466d-aed7-bdabe8b69aff"
observer.health.GENERATION = "222870ba-ad3c-4cf5-a6de-e1b3a52ab5bc"
observer.health.ROUTE_REVISION = 273
observer.health.GROUP_REVISION = 300
observer.health.DEFINITION_REVISION = 211
observer.health.OUTCOME = "CX_HEALTH_OBSERVATION_GREEN"
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
