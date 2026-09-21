#!/usr/bin/env python3
"""Read-only CV lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cv_replacement_recovery as cv_replacement


observer.health.replacement = cv_replacement.replacement
observer.health.STATE = cv_replacement.replacement.STATE
observer.health.OPERATION = "29511d3b-0921-4ce3-9c55-34cbe531f678"
observer.health.INSTALLATION_LABEL = "cv"
observer.health.INSTALLATION_ID = "f94149ca-a01e-4a20-836f-3f5132e0dbb7"
observer.health.GENERATION = "82aec2b8-072d-4f2e-9624-f9539c8890a6"
observer.health.ROUTE_REVISION = 267
observer.health.GROUP_REVISION = 294
observer.health.DEFINITION_REVISION = 205
observer.health.OUTCOME = "CV_HEALTH_OBSERVATION_GREEN"
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
