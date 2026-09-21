#!/usr/bin/env python3
"""Read-only DB lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_db_replacement_recovery as db_replacement


observer.health.replacement = db_replacement.replacement
observer.health.STATE = db_replacement.replacement.STATE
observer.health.OPERATION = "d9ec3d43-d5a3-46e6-b1f9-c9036a29c764"
observer.health.INSTALLATION_LABEL = "db"
observer.health.INSTALLATION_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"
observer.health.GENERATION = "c1ae6205-0743-483c-82e3-1d1c95b1ab31"
observer.health.ROUTE_REVISION = 285
observer.health.GROUP_REVISION = 312
observer.health.DEFINITION_REVISION = 223
observer.health.OUTCOME = "DB_HEALTH_OBSERVATION_GREEN"
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
