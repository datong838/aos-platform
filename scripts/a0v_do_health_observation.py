#!/usr/bin/env python3
"""Read-only DO lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_do_replacement_recovery as do_replacement


observer.health.replacement = do_replacement.replacement
observer.health.STATE = do_replacement.replacement.STATE
observer.health.OPERATION = "9e0c395e-f2a6-4d64-bb3a-19b7765b118e"
observer.health.INSTALLATION_LABEL = "do"
observer.health.INSTALLATION_ID = "e748c240-f9d4-47c0-a9dc-3c473b311cae"
observer.health.GENERATION = "93b514ad-3920-4eb4-8fc7-7cb1106254ff"
observer.health.BINDING_REVISION = 6
observer.health.EXECUTION_EPOCH = 3
observer.health.ROUTE_REVISION = 324
observer.health.GROUP_REVISION = 351
observer.health.DEFINITION_REVISION = 262
observer.health.OUTCOME = "DO_HEALTH_OBSERVATION_GREEN"
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
