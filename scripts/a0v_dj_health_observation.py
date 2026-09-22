#!/usr/bin/env python3
"""Read-only DJ lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_dj_replacement_recovery as dj_replacement


observer.health.replacement = dj_replacement.replacement
observer.health.STATE = dj_replacement.replacement.STATE
observer.health.OPERATION = "dfef9147-6c08-4a7a-b128-6100838048f1"
observer.health.INSTALLATION_LABEL = "dj"
observer.health.INSTALLATION_ID = "aca93a08-341f-4bd6-9e94-ed7fde3aed66"
observer.health.GENERATION = "6ce73106-f945-4d34-a818-552303fec308"
observer.health.ROUTE_REVISION = 309
observer.health.GROUP_REVISION = 336
observer.health.DEFINITION_REVISION = 247
observer.health.OUTCOME = "DJ_HEALTH_OBSERVATION_GREEN"
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
