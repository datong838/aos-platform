#!/usr/bin/env python3
"""Exact internal CB cutover from CA-detached group233."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cb_successor_business as cb_successor

cutover.successor = cb_successor
cutover.STATE = cb_successor.STATE.parent / "cutover-cb"
cutover.OPERATION = "8da61041-939b-4cb9-a1e9-fbc8ac87effd"
cutover.PREFIX = "a0v-qyh-clean-generation-cb-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 233
_target = cutover.target
def _cb_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})
cutover.target = _cb_target
def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CB_")}
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cb_successor.setup()), ensure_ascii=False, indent=2, default=str))
