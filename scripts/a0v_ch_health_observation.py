#!/usr/bin/env python3
"""Read-only CH lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_ch_replacement_recovery as ch_replacement


observer.health.replacement = ch_replacement.replacement
observer.health.STATE = ch_replacement.replacement.STATE
observer.health.OPERATION = "efed6af4-3243-47fd-83ef-8d870cddc3ea"
observer.health.INSTALLATION_LABEL = "ch"
observer.health.INSTALLATION_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"
observer.health.GENERATION = "0521ccf8-304a-45b3-b820-dc6ebd64b51b"
observer.health.ROUTE_REVISION = 225
observer.health.GROUP_REVISION = 252
observer.health.DEFINITION_REVISION = 166
observer.health.OUTCOME = "CH_HEALTH_OBSERVATION_GREEN"
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
