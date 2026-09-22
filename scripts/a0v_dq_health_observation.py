#!/usr/bin/env python3
"""Read-only DQ lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dq_replacement_recovery as dq_replacement


observer.health.replacement = dq_replacement.replacement
observer.health.STATE = dq_replacement.replacement.STATE
observer.health.OPERATION = "2209ba48-7051-4349-bc80-51f2b340c48d"
observer.health.INSTALLATION_LABEL = "dq"
observer.health.INSTALLATION_ID = "29e553b2-3afc-4b15-b860-f79104f3491a"
observer.health.GENERATION = "b8d6900d-b4a3-43d8-8891-a4b1d02abd3c"
observer.health.BINDING_REVISION = 6
observer.health.EXECUTION_EPOCH = 3
observer.health.ROUTE_REVISION = 330
observer.health.GROUP_REVISION = 357
observer.health.DEFINITION_REVISION = 268
observer.health.OUTCOME = "DQ_HEALTH_OBSERVATION_GREEN"
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
