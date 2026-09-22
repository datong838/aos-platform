#!/usr/bin/env python3
"""Read-only DP lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dp_replacement_recovery as dp_replacement


observer.health.replacement = dp_replacement.replacement
observer.health.STATE = dp_replacement.replacement.STATE
observer.health.OPERATION = "9893b31e-aacb-4d6b-8553-e62d3db659d6"
observer.health.INSTALLATION_LABEL = "dp"
observer.health.INSTALLATION_ID = "d2d3c478-f9d9-4489-92b7-1de57f546452"
observer.health.GENERATION = "b15f1733-89dd-4684-9475-9fba095a1d74"
observer.health.BINDING_REVISION = 6
observer.health.EXECUTION_EPOCH = 3
observer.health.ROUTE_REVISION = 327
observer.health.GROUP_REVISION = 354
observer.health.DEFINITION_REVISION = 265
observer.health.OUTCOME = "DP_HEALTH_OBSERVATION_GREEN"
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
