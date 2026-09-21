#!/usr/bin/env python3
"""Read-only CG lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cg_replacement_recovery as cg_replacement


observer.health.replacement = cg_replacement.replacement
observer.health.STATE = cg_replacement.replacement.STATE
observer.health.OPERATION = "a5b894bb-0a51-4487-a738-651c60ac7505"
observer.health.INSTALLATION_LABEL = "cg"
observer.health.INSTALLATION_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"
observer.health.GENERATION = "3ed300fa-5fff-4949-9fb0-1926412e51ae"
observer.health.ROUTE_REVISION = 222
observer.health.GROUP_REVISION = 249
observer.health.DEFINITION_REVISION = 163
observer.health.OUTCOME = "CG_HEALTH_OBSERVATION_GREEN"
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
