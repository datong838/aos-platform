#!/usr/bin/env python3
"""Exact internal CU cutover from CT-detached group290."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cu_successor_business as cu_successor

cutover.successor = cu_successor
cutover.STATE = cu_successor.STATE.parent / "cutover-cu"
cutover.OPERATION = "ef453252-1d89-4f02-8f3f-3a05c79d6293"
cutover.PREFIX = "a0v-qyh-clean-generation-cu-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 290
_target = cutover.target


def _cu_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cu_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CU_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cu_successor.setup()), ensure_ascii=False, indent=2, default=str))
