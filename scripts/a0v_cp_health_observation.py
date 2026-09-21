#!/usr/bin/env python3
"""Read-only CP lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cp_replacement_recovery as cp_replacement


observer.health.replacement = cp_replacement.replacement
observer.health.STATE = cp_replacement.replacement.STATE
observer.health.OPERATION = "ca822e5b-c389-4609-8ca7-4dcdcb7c016c"
observer.health.INSTALLATION_LABEL = "cp"
observer.health.INSTALLATION_ID = "1d8b71c5-1cde-4d16-b16f-835f92bf8663"
observer.health.GENERATION = "9b0201fc-9822-4527-b63c-23cbd416057d"
observer.health.ROUTE_REVISION = 249
observer.health.GROUP_REVISION = 276
observer.health.DEFINITION_REVISION = 190
observer.health.OUTCOME = "CP_HEALTH_OBSERVATION_GREEN"
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
