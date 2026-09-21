#!/usr/bin/env python3
"""Read-only CO lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_co_replacement_recovery as co_replacement


observer.health.replacement = co_replacement.replacement
observer.health.STATE = co_replacement.replacement.STATE
observer.health.OPERATION = "d05101eb-707f-45b2-84f8-f43a5c80d69c"
observer.health.INSTALLATION_LABEL = "co"
observer.health.INSTALLATION_ID = "648b267b-bb8f-4582-ab29-288279f534c7"
observer.health.GENERATION = "db428c1b-2fe4-4869-8a69-ddffaa909ba7"
observer.health.ROUTE_REVISION = 246
observer.health.GROUP_REVISION = 273
observer.health.DEFINITION_REVISION = 187
observer.health.OUTCOME = "CO_HEALTH_OBSERVATION_GREEN"
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
