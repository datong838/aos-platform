#!/usr/bin/env python3
"""Exact internal DR cutover from DQ-detached group359."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dr_successor_business as dr_successor

cutover.successor = dr_successor.successor
cutover.STATE = dr_successor.STATE.parent / "cutover-dr"
cutover.OPERATION = "dda8a767-fc27-4c43-9674-b6bc5708017e"
cutover.PREFIX = "a0v-qyh-clean-generation-dr-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 359
_target = cutover.target


def _dr_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dr_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DR_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dr_successor.setup()), ensure_ascii=False, indent=2, default=str))
