#!/usr/bin/env python3
"""Exact internal BU cutover from BT-detached group212."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_bu_successor_business as bu_successor

cutover.successor = bu_successor
cutover.STATE = bu_successor.STATE.parent / "cutover-bu"
cutover.OPERATION = "ec731e19-1161-451c-8585-9c59849ea6c0"
cutover.PREFIX = "a0v-qyh-clean-generation-bu-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 212
_target = cutover.target

def _bu_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})

cutover.target = _bu_target

def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BU_")}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bu_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
