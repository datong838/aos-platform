#!/usr/bin/env python3
"""Read-only CY lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cy_replacement_recovery as cy_replacement


observer.health.replacement = cy_replacement.replacement
observer.health.STATE = cy_replacement.replacement.STATE
observer.health.OPERATION = "37e60676-612b-4632-86a8-82e0869512c7"
observer.health.INSTALLATION_LABEL = "cy"
observer.health.INSTALLATION_ID = "917cd341-96a5-4428-9508-03c716c587ad"
observer.health.GENERATION = "a2fdbdb1-430c-417b-969d-6bd30874d38c"
observer.health.ROUTE_REVISION = 276
observer.health.GROUP_REVISION = 303
observer.health.DEFINITION_REVISION = 214
observer.health.OUTCOME = "CY_HEALTH_OBSERVATION_GREEN"
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
