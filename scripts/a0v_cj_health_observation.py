#!/usr/bin/env python3
"""Read-only CJ lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cj_replacement_recovery as cj_replacement


observer.health.replacement = cj_replacement.replacement
observer.health.STATE = cj_replacement.replacement.STATE
observer.health.OPERATION = "8a148985-7582-4c10-b514-cc7e01359ac0"
observer.health.INSTALLATION_LABEL = "cj"
observer.health.INSTALLATION_ID = "184e0d1d-128a-462c-b677-d19bc5bf0891"
observer.health.GENERATION = "f45f46a9-56ae-49b5-966d-083cdf19282b"
observer.health.ROUTE_REVISION = 231
observer.health.GROUP_REVISION = 258
observer.health.DEFINITION_REVISION = 172
observer.health.OUTCOME = "CJ_HEALTH_OBSERVATION_GREEN"
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
