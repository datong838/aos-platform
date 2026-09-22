#!/usr/bin/env python3
"""Read-only DE lease observation through the validated repeatable-read observer."""
from __future__ import annotations

import argparse
import json

import a0v_bx_health_observation as observer
import a0v_de_replacement_recovery as de_replacement


observer.health.replacement = de_replacement.replacement
observer.health.STATE = de_replacement.replacement.STATE
observer.health.OPERATION = "b7f95379-29b4-419b-8360-c211387812e8"
observer.health.INSTALLATION_LABEL = "de"
observer.health.INSTALLATION_ID = "5d993078-18ec-4302-9286-7081a1463cc0"
observer.health.GENERATION = "f5181ad4-e304-4533-aa4a-0f30b3c6dac3"
observer.health.ROUTE_REVISION = 294
observer.health.GROUP_REVISION = 321
observer.health.DEFINITION_REVISION = 232
observer.health.OUTCOME = "DE_HEALTH_OBSERVATION_GREEN"
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
