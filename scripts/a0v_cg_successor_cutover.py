#!/usr/bin/env python3
"""Exact internal CG cutover from CF-detached group248."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cg_successor_business as cg_successor

cutover.successor = cg_successor
cutover.STATE = cg_successor.STATE.parent / "cutover-cg"
cutover.OPERATION = "d8dbb6b2-7fdf-424a-b95f-63513ca37e06"
cutover.PREFIX = "a0v-qyh-clean-generation-cg-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 248
_target = cutover.target
def _cg_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})
cutover.target = _cg_target
def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CG_")}
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cg_successor.setup()), ensure_ascii=False, indent=2, default=str))
