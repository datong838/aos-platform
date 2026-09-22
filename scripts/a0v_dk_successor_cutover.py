#!/usr/bin/env python3
"""Exact internal DK cutover from DJ-detached group338."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dk_successor_business as dk_successor

cutover.successor = dk_successor
cutover.STATE = dk_successor.STATE.parent / "cutover-dk"
cutover.OPERATION = "aeaabf9f-fb1b-49f3-b012-97fa0762378b"
cutover.PREFIX = "a0v-qyh-clean-generation-dk-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 338
_target = cutover.target


def _dk_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dk_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DK_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dk_successor.setup()), ensure_ascii=False, indent=2, default=str))
