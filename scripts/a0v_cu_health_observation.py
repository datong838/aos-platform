#!/usr/bin/env python3
"""Read-only CU lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cu_replacement_recovery as cu_replacement


observer.health.replacement = cu_replacement.replacement
observer.health.STATE = cu_replacement.replacement.STATE
observer.health.OPERATION = "1bc0569b-be26-4ee5-81d2-631f2ec26885"
observer.health.INSTALLATION_LABEL = "cu"
observer.health.INSTALLATION_ID = "2c2d5506-1f80-4557-bf4b-00ead0258002"
observer.health.GENERATION = "bcaa7ea0-62b1-4238-8615-28db45e3014e"
observer.health.ROUTE_REVISION = 264
observer.health.GROUP_REVISION = 291
observer.health.DEFINITION_REVISION = 202
observer.health.OUTCOME = "CU_HEALTH_OBSERVATION_GREEN"
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
