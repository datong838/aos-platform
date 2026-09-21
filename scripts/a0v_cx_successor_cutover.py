#!/usr/bin/env python3
"""Exact internal CX cutover from CW-detached group299."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cx_successor_business as cx_successor

cutover.successor = cx_successor
cutover.STATE = cx_successor.STATE.parent / "cutover-cx"
cutover.OPERATION = "686de66e-fb8f-41c9-ad9d-188bca013a92"
cutover.PREFIX = "a0v-qyh-clean-generation-cx-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 299
_target = cutover.target


def _cx_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cx_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CX_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cx_successor.setup()), ensure_ascii=False, indent=2, default=str))
