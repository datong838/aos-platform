#!/usr/bin/env python3
"""Read-only DH lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dh_replacement_recovery as dh_replacement


observer.health.replacement = dh_replacement.replacement
observer.health.STATE = dh_replacement.replacement.STATE
observer.health.OPERATION = "4b223bbb-771e-4d94-bd65-c25dd6ae20e4"
observer.health.INSTALLATION_LABEL = "dh"
observer.health.INSTALLATION_ID = "10d583ad-96ee-4b1a-bb18-92e428abe16e"
observer.health.GENERATION = "107a24f5-691d-4f2a-9b46-4e7b21938146"
observer.health.ROUTE_REVISION = 303
observer.health.GROUP_REVISION = 330
observer.health.DEFINITION_REVISION = 241
observer.health.OUTCOME = "DH_HEALTH_OBSERVATION_GREEN"
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
