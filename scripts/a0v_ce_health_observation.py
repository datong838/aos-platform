#!/usr/bin/env python3
"""Read-only CE lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_ce_replacement_recovery as ce_replacement


observer.health.replacement = ce_replacement.replacement
observer.health.STATE = ce_replacement.replacement.STATE
observer.health.OPERATION = "706dfb14-3c55-472e-9d69-ea49866727ad"
observer.health.INSTALLATION_LABEL = "ce"
observer.health.INSTALLATION_ID = "29d1b06d-3baa-4476-9cf8-5ea345d134c7"
observer.health.GENERATION = "e51d0010-d57f-4f5c-8f7e-7a1d732bebf7"
observer.health.ROUTE_REVISION = 216
observer.health.GROUP_REVISION = 243
observer.health.DEFINITION_REVISION = 157
observer.health.OUTCOME = "CE_HEALTH_OBSERVATION_GREEN"
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
