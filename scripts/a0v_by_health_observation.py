#!/usr/bin/env python3
"""Read-only BY lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_by_replacement_recovery as by_replacement


observer.health.replacement = by_replacement.replacement
observer.health.STATE = by_replacement.replacement.STATE
observer.health.OPERATION = "5e67db87-80a8-40cc-8a55-38e292f4f7a4"
observer.health.INSTALLATION_LABEL = "by"
observer.health.INSTALLATION_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"
observer.health.GENERATION = "01f99334-0515-4c73-b442-a293709b3cc2"
observer.health.ROUTE_REVISION = 198
observer.health.GROUP_REVISION = 225
observer.health.DEFINITION_REVISION = 139
observer.health.OUTCOME = "BY_HEALTH_OBSERVATION_GREEN"
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
