#!/usr/bin/env python3
"""Read-only CD lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cd_replacement_recovery as cd_replacement


observer.health.replacement = cd_replacement.replacement
observer.health.STATE = cd_replacement.replacement.STATE
observer.health.OPERATION = "0450e182-c811-4282-bccc-203a918a9561"
observer.health.INSTALLATION_LABEL = "cd"
observer.health.INSTALLATION_ID = "01b41c17-fce2-4bcf-8d9e-a48d2d4bf743"
observer.health.GENERATION = "22639b06-1211-424d-9f64-696822e0add4"
observer.health.ROUTE_REVISION = 213
observer.health.GROUP_REVISION = 240
observer.health.DEFINITION_REVISION = 154
observer.health.OUTCOME = "CD_HEALTH_OBSERVATION_GREEN"
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
