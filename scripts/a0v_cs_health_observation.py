#!/usr/bin/env python3
"""Read-only CS lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cs_replacement_recovery as cs_replacement


observer.health.replacement = cs_replacement.replacement
observer.health.STATE = cs_replacement.replacement.STATE
observer.health.OPERATION = "7b8e60bf-8cb6-4e6a-9a50-05f6e3b4fc3c"
observer.health.INSTALLATION_LABEL = "cs"
observer.health.INSTALLATION_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"
observer.health.GENERATION = "01a1719d-1109-440f-a233-1c5a6adb0d81"
observer.health.ROUTE_REVISION = 258
observer.health.GROUP_REVISION = 285
observer.health.DEFINITION_REVISION = 196
observer.health.OUTCOME = "CS_HEALTH_OBSERVATION_GREEN"
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
