#!/usr/bin/env python3
"""Exact internal DQ cutover from DP-detached group356."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dq_successor_business as dq_successor

cutover.successor = dq_successor
cutover.STATE = dq_successor.STATE.parent / "cutover-dq"
cutover.OPERATION = "13efdb15-7a6e-4415-92c8-0d5f3852fd6d"
cutover.PREFIX = "a0v-qyh-clean-generation-dq-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 356
_target = cutover.target


def _dq_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dq_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DQ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dq_successor.setup()), ensure_ascii=False, indent=2, default=str))
