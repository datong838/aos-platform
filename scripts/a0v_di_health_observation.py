#!/usr/bin/env python3
"""Read-only DI lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_di_replacement_recovery as di_replacement


observer.health.replacement = di_replacement.replacement
observer.health.STATE = di_replacement.replacement.STATE
observer.health.OPERATION = "d366b2d3-9456-4178-9a21-cc516cca507d"
observer.health.INSTALLATION_LABEL = "di"
observer.health.INSTALLATION_ID = "c8298a5d-9d94-4c37-81c9-508e2f0faf60"
observer.health.GENERATION = "56950fc1-4007-497a-8a09-df133a1950c1"
observer.health.ROUTE_REVISION = 306
observer.health.GROUP_REVISION = 333
observer.health.DEFINITION_REVISION = 244
observer.health.OUTCOME = "DI_HEALTH_OBSERVATION_GREEN"
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
