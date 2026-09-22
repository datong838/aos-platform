#!/usr/bin/env python3
"""Read-only DD lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dd_replacement_recovery as dd_replacement


observer.health.replacement = dd_replacement.replacement
observer.health.STATE = dd_replacement.replacement.STATE
observer.health.OPERATION = "76d2a6e1-1e7a-41cc-bbe4-df3d50e3d346"
observer.health.INSTALLATION_LABEL = "dd"
observer.health.INSTALLATION_ID = "6e05658b-5d0a-40ae-ab8e-81fcca5269db"
observer.health.GENERATION = "422d2d5b-752a-4182-b1e8-831a8f63c2a1"
observer.health.ROUTE_REVISION = 291
observer.health.GROUP_REVISION = 318
observer.health.DEFINITION_REVISION = 229
observer.health.OUTCOME = "DD_HEALTH_OBSERVATION_GREEN"
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
