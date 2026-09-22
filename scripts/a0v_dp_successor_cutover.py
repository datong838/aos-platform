#!/usr/bin/env python3
"""Exact internal DP cutover from DO-detached group353."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dp_successor_business as dp_successor

cutover.successor = dp_successor
cutover.STATE = dp_successor.STATE.parent / "cutover-dp"
cutover.OPERATION = "29f2f093-aa25-435d-bc93-1e81ea959059"
cutover.PREFIX = "a0v-qyh-clean-generation-dp-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 353
_target = cutover.target


def _dp_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dp_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DP_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dp_successor.setup()), ensure_ascii=False, indent=2, default=str))
