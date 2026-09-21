#!/usr/bin/env python3
"""Read-only CR lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cr_replacement_recovery as cr_replacement


observer.health.replacement = cr_replacement.replacement
observer.health.STATE = cr_replacement.replacement.STATE
observer.health.OPERATION = "38aadd42-6693-467f-abde-cc36924fef2f"
observer.health.INSTALLATION_LABEL = "cr"
observer.health.INSTALLATION_ID = "913cb7a1-4912-471a-abbf-452e3ce999a9"
observer.health.GENERATION = "a4a16448-5581-4948-b962-777ff601e855"
observer.health.ROUTE_REVISION = 255
observer.health.GROUP_REVISION = 282
observer.health.DEFINITION_REVISION = 193
observer.health.OUTCOME = "CR_HEALTH_OBSERVATION_GREEN"
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
