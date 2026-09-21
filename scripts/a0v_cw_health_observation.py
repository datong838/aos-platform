#!/usr/bin/env python3
"""Read-only CW lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cw_replacement_recovery as cw_replacement


observer.health.replacement = cw_replacement.replacement
observer.health.STATE = cw_replacement.replacement.STATE
observer.health.OPERATION = "65d2b402-68f8-4294-b42c-5585894c6e57"
observer.health.INSTALLATION_LABEL = "cw"
observer.health.INSTALLATION_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"
observer.health.GENERATION = "a60036f1-5887-4157-ad32-616925b547bf"
observer.health.ROUTE_REVISION = 270
observer.health.GROUP_REVISION = 297
observer.health.DEFINITION_REVISION = 208
observer.health.OUTCOME = "CW_HEALTH_OBSERVATION_GREEN"
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
