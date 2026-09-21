#!/usr/bin/env python3
"""Read-only CK lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_ck_replacement_recovery as ck_replacement


observer.health.replacement = ck_replacement.replacement
observer.health.STATE = ck_replacement.replacement.STATE
observer.health.OPERATION = "e60b3ca6-bdc2-40a6-9928-5ec574f35917"
observer.health.INSTALLATION_LABEL = "ck"
observer.health.INSTALLATION_ID = "c1cb44ba-68ae-4d32-9974-5f031554fed2"
observer.health.GENERATION = "1edb1688-e2b6-42f0-b513-849ae372859e"
observer.health.ROUTE_REVISION = 234
observer.health.GROUP_REVISION = 261
observer.health.DEFINITION_REVISION = 175
observer.health.OUTCOME = "CK_HEALTH_OBSERVATION_GREEN"
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
