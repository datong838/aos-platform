#!/usr/bin/env python3
"""Read-only DL lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dl_replacement_recovery as dl_replacement


observer.health.replacement = dl_replacement.replacement
observer.health.STATE = dl_replacement.replacement.STATE
observer.health.OPERATION = "a0a02705-3d34-4520-b5b8-cf0ef8777fc6"
observer.health.INSTALLATION_LABEL = "dl"
observer.health.INSTALLATION_ID = "83453fb3-8c39-422c-845b-e152551e0a30"
observer.health.GENERATION = "f3a1f381-5aeb-4494-a155-164e0ef9e0f5"
observer.health.ROUTE_REVISION = 315
observer.health.GROUP_REVISION = 342
observer.health.DEFINITION_REVISION = 253
observer.health.OUTCOME = "DL_HEALTH_OBSERVATION_GREEN"
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
