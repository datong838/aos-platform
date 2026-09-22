#!/usr/bin/env python3
"""Read-only DF lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_df_replacement_recovery as df_replacement


observer.health.replacement = df_replacement.replacement
observer.health.STATE = df_replacement.replacement.STATE
observer.health.OPERATION = "a17c3056-4740-47d8-9452-b088fbc59dee"
observer.health.INSTALLATION_LABEL = "df"
observer.health.INSTALLATION_ID = "a0639f78-af04-4249-97f6-d8507de45f44"
observer.health.GENERATION = "ec18c8c6-2694-44c1-a9c9-ea79ea606e45"
observer.health.ROUTE_REVISION = 297
observer.health.GROUP_REVISION = 324
observer.health.DEFINITION_REVISION = 235
observer.health.OUTCOME = "DF_HEALTH_OBSERVATION_GREEN"
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
