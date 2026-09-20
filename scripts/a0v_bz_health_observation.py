#!/usr/bin/env python3
"""Read-only BZ lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_bz_replacement_recovery as bz_replacement


observer.health.replacement = bz_replacement.replacement
observer.health.STATE = bz_replacement.replacement.STATE
observer.health.OPERATION = "71d642ec-f53a-46f2-94b7-9500babfc594"
observer.health.INSTALLATION_LABEL = "bz"
observer.health.INSTALLATION_ID = "9b30837c-da4d-4cfd-b438-de40aa5e3d7a"
observer.health.GENERATION = "6f1e6e77-24aa-4052-9102-88e4a432fe55"
observer.health.ROUTE_REVISION = 201
observer.health.GROUP_REVISION = 228
observer.health.DEFINITION_REVISION = 142
observer.health.OUTCOME = "BZ_HEALTH_OBSERVATION_GREEN"
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
