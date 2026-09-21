#!/usr/bin/env python3
"""Read-only CQ lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cq_replacement_recovery as cq_replacement


observer.health.replacement = cq_replacement.replacement
observer.health.STATE = cq_replacement.replacement.STATE
observer.health.OPERATION = "2069f6d3-1b40-4f06-9aff-62febe156943"
observer.health.INSTALLATION_LABEL = "cq"
observer.health.INSTALLATION_ID = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"
observer.health.GENERATION = "ae8a1005-99fb-48c5-9dfe-8f76590bc0c8"
observer.health.ROUTE_REVISION = 252
observer.health.GROUP_REVISION = 279
observer.health.DEFINITION_REVISION = 193
observer.health.OUTCOME = "CQ_HEALTH_OBSERVATION_GREEN"
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
