#!/usr/bin/env python3
"""Read-only CN lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cn_replacement_recovery as cn_replacement


observer.health.replacement = cn_replacement.replacement
observer.health.STATE = cn_replacement.replacement.STATE
observer.health.OPERATION = "4ba3f9c1-7480-48f5-ab79-e4f167968012"
observer.health.INSTALLATION_LABEL = "cn"
observer.health.INSTALLATION_ID = "1366f4dd-47d9-42c1-b26a-759c7bd556da"
observer.health.GENERATION = "cd0601e0-2668-496d-9f93-561d2e69a170"
observer.health.ROUTE_REVISION = 243
observer.health.GROUP_REVISION = 270
observer.health.DEFINITION_REVISION = 184
observer.health.OUTCOME = "CN_HEALTH_OBSERVATION_GREEN"
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
