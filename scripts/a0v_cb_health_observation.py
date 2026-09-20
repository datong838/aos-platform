#!/usr/bin/env python3
"""Read-only CB lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_cb_replacement_recovery as cb_replacement


observer.health.replacement = cb_replacement.replacement
observer.health.STATE = cb_replacement.replacement.STATE
observer.health.OPERATION = "c2645b92-40b0-41e4-a383-d76bdc772017"
observer.health.INSTALLATION_LABEL = "cb"
observer.health.INSTALLATION_ID = "3d6df614-5a05-4c6f-823e-688d81e84096"
observer.health.GENERATION = "0cceac8c-c831-4b3f-92c3-fc35240c5414"
observer.health.ROUTE_REVISION = 207
observer.health.GROUP_REVISION = 234
observer.health.DEFINITION_REVISION = 148
observer.health.OUTCOME = "CB_HEALTH_OBSERVATION_GREEN"
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
