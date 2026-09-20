#!/usr/bin/env python3
"""Read-only CA lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_ca_replacement_recovery as ca_replacement


observer.health.replacement = ca_replacement.replacement
observer.health.STATE = ca_replacement.replacement.STATE
observer.health.OPERATION = "69cda7b1-dd65-4fee-b3c1-30225a7a8f3f"
observer.health.INSTALLATION_LABEL = "ca"
observer.health.INSTALLATION_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"
observer.health.GENERATION = "1f18a077-12c6-4242-982a-0c3fa1159540"
observer.health.ROUTE_REVISION = 204
observer.health.GROUP_REVISION = 231
observer.health.DEFINITION_REVISION = 145
observer.health.OUTCOME = "CA_HEALTH_OBSERVATION_GREEN"
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
