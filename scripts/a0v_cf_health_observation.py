#!/usr/bin/env python3
"""Read-only CF lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cf_replacement_recovery as cf_replacement


observer.health.replacement = cf_replacement.replacement
observer.health.STATE = cf_replacement.replacement.STATE
observer.health.OPERATION = "f8c49bee-1e87-4d64-be32-e683e84dbb59"
observer.health.INSTALLATION_LABEL = "cf"
observer.health.INSTALLATION_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"
observer.health.GENERATION = "88996259-ad79-4aa6-962c-c29a24559db8"
observer.health.ROUTE_REVISION = 219
observer.health.GROUP_REVISION = 246
observer.health.DEFINITION_REVISION = 160
observer.health.OUTCOME = "CF_HEALTH_OBSERVATION_GREEN"
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
