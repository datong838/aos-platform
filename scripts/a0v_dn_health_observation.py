#!/usr/bin/env python3
"""Read-only DN lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dn_replacement_recovery as dn_replacement


observer.health.replacement = dn_replacement.replacement
observer.health.STATE = dn_replacement.replacement.STATE
observer.health.OPERATION = "7c3a1ce9-d0c5-453d-ae61-1d862de8a3b0"
observer.health.INSTALLATION_LABEL = "dn"
observer.health.INSTALLATION_ID = "2cb67f0a-0970-4d75-9c4a-a19d68563a3e"
observer.health.GENERATION = "e8b25248-98fc-475b-bf9e-1e7e3e803ec7"
observer.health.BINDING_REVISION = 6
observer.health.EXECUTION_EPOCH = 3
observer.health.ROUTE_REVISION = 321
observer.health.GROUP_REVISION = 348
observer.health.DEFINITION_REVISION = 259
observer.health.OUTCOME = "DN_HEALTH_OBSERVATION_GREEN"
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
