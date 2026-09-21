#!/usr/bin/env python3
"""Read-only DC lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dc_replacement_recovery as dc_replacement


observer.health.replacement = dc_replacement.replacement
observer.health.STATE = dc_replacement.replacement.STATE
observer.health.OPERATION = "66cdef5b-6105-40b1-ab79-7343f38f1438"
observer.health.INSTALLATION_LABEL = "dc"
observer.health.INSTALLATION_ID = "02d39eb8-174e-432f-9776-57de7c4436c8"
observer.health.GENERATION = "bd59503f-eb9e-4fe6-a09d-a92a3b924682"
observer.health.ROUTE_REVISION = 288
observer.health.GROUP_REVISION = 315
observer.health.DEFINITION_REVISION = 226
observer.health.OUTCOME = "DC_HEALTH_OBSERVATION_GREEN"
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
