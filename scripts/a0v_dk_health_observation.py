#!/usr/bin/env python3
"""Read-only DK lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dk_replacement_recovery as dk_replacement


observer.health.replacement = dk_replacement.replacement
observer.health.STATE = dk_replacement.replacement.STATE
observer.health.OPERATION = "25492237-07ae-4288-91ca-a54c1d50651c"
observer.health.INSTALLATION_LABEL = "dk"
observer.health.INSTALLATION_ID = "b651f4d7-b2a3-4032-a0d2-9b43743deb07"
observer.health.GENERATION = "fb16d08b-8fcb-4eb0-8c13-7698d16b83b4"
observer.health.ROUTE_REVISION = 312
observer.health.GROUP_REVISION = 339
observer.health.DEFINITION_REVISION = 250
observer.health.OUTCOME = "DK_HEALTH_OBSERVATION_GREEN"
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
