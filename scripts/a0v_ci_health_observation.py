#!/usr/bin/env python3
"""Read-only CI lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_ci_replacement_recovery as ci_replacement


observer.health.replacement = ci_replacement.replacement
observer.health.STATE = ci_replacement.replacement.STATE
observer.health.OPERATION = "473dc4ab-42af-4dbd-95bf-67beaa6a1f3e"
observer.health.INSTALLATION_LABEL = "ci"
observer.health.INSTALLATION_ID = "1b9f500d-48a0-4f2c-8284-3db26e5cd4e7"
observer.health.GENERATION = "8de8994b-ad87-4039-a851-d944153bca08"
observer.health.ROUTE_REVISION = 228
observer.health.GROUP_REVISION = 255
observer.health.DEFINITION_REVISION = 169
observer.health.OUTCOME = "CI_HEALTH_OBSERVATION_GREEN"
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
