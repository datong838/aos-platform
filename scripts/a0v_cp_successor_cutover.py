#!/usr/bin/env python3
"""Exact internal CP cutover from CO-detached group275."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cp_successor_business as cp_successor

cutover.successor = cp_successor
cutover.STATE = cp_successor.STATE.parent / "cutover-cp"
cutover.OPERATION = "ec6199e0-1a5f-4d63-a44b-bd1e8cfe69bd"
cutover.PREFIX = "a0v-qyh-clean-generation-cp-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 275
_target = cutover.target


def _cp_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cp_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CP_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cp_successor.setup()), ensure_ascii=False, indent=2, default=str))
