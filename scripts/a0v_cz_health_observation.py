#!/usr/bin/env python3
"""Read-only CZ lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cz_replacement_recovery as cz_replacement


observer.health.replacement = cz_replacement.replacement
observer.health.STATE = cz_replacement.replacement.STATE
observer.health.OPERATION = "b8bbb317-8b55-4fd4-994c-6a3ae33ccd65"
observer.health.INSTALLATION_LABEL = "cz"
observer.health.INSTALLATION_ID = "162e4c29-a24e-4c6b-8da7-9582d090d708"
observer.health.GENERATION = "d1b0f7eb-9677-4d52-a656-a4ae28942976"
observer.health.ROUTE_REVISION = 279
observer.health.GROUP_REVISION = 306
observer.health.DEFINITION_REVISION = 217
observer.health.OUTCOME = "CZ_HEALTH_OBSERVATION_GREEN"
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
