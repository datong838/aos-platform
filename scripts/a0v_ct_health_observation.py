#!/usr/bin/env python3
"""Read-only CT lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_ct_replacement_recovery as ct_replacement


observer.health.replacement = ct_replacement.replacement
observer.health.STATE = ct_replacement.replacement.STATE
observer.health.OPERATION = "31b9552d-d58f-48e8-a905-2534fe334ef5"
observer.health.INSTALLATION_LABEL = "ct"
observer.health.INSTALLATION_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"
observer.health.GENERATION = "0d234db2-8b76-4ec8-a14a-a8c6eec9bbc6"
observer.health.ROUTE_REVISION = 261
observer.health.GROUP_REVISION = 288
observer.health.DEFINITION_REVISION = 199
observer.health.OUTCOME = "CT_HEALTH_OBSERVATION_GREEN"
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
