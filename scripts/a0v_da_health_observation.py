#!/usr/bin/env python3
"""Read-only DA lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_da_replacement_recovery as da_replacement


observer.health.replacement = da_replacement.replacement
observer.health.STATE = da_replacement.replacement.STATE
observer.health.OPERATION = "e00139ad-ae87-4047-8184-626e93d27b4f"
observer.health.INSTALLATION_LABEL = "da"
observer.health.INSTALLATION_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"
observer.health.GENERATION = "dbcdd8cb-c6f4-47cc-91f9-1662f54044c0"
observer.health.ROUTE_REVISION = 282
observer.health.GROUP_REVISION = 309
observer.health.DEFINITION_REVISION = 220
observer.health.OUTCOME = "DA_HEALTH_OBSERVATION_GREEN"
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
