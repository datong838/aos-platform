#!/usr/bin/env python3
"""Exact internal CC cutover from CB-detached group236."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cc_successor_business as cc_successor

cutover.successor = cc_successor
cutover.STATE = cc_successor.STATE.parent / "cutover-cc"
cutover.OPERATION = "7cd9744d-fdee-46a9-b152-1bfa6129c77d"
cutover.PREFIX = "a0v-qyh-clean-generation-cc-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 236
_target = cutover.target
def _cc_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})
cutover.target = _cc_target
def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CC_")}
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cc_successor.setup()), ensure_ascii=False, indent=2, default=str))
