#!/usr/bin/env python3
"""Read-only DG lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dg_replacement_recovery as dg_replacement


observer.health.replacement = dg_replacement.replacement
observer.health.STATE = dg_replacement.replacement.STATE
observer.health.OPERATION = "8f8be2e1-3655-4a53-bfb6-0d2de164ebfe"
observer.health.INSTALLATION_LABEL = "dg"
observer.health.INSTALLATION_ID = "d551d104-f240-4b27-b738-1ef47129b5a4"
observer.health.GENERATION = "6c1780ab-746b-4303-a9ad-dc30039af8a4"
observer.health.ROUTE_REVISION = 300
observer.health.GROUP_REVISION = 327
observer.health.DEFINITION_REVISION = 238
observer.health.OUTCOME = "DG_HEALTH_OBSERVATION_GREEN"
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
