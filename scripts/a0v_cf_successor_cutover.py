#!/usr/bin/env python3
"""Exact internal CF cutover from CE-detached group245."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cf_successor_business as cf_successor

cutover.successor = cf_successor
cutover.STATE = cf_successor.STATE.parent / "cutover-cf"
cutover.OPERATION = "41853ebd-b68f-4db6-aeda-ac9c765be324"
cutover.PREFIX = "a0v-qyh-clean-generation-cf-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 245
_target = cutover.target
def _cf_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})
cutover.target = _cf_target
def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CF_")}
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cf_successor.setup()), ensure_ascii=False, indent=2, default=str))
