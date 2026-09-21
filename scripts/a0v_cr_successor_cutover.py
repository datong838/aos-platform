#!/usr/bin/env python3
"""Exact internal CR cutover from CQ-detached group281."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cr_successor_business as cr_successor

cutover.successor = cr_successor
cutover.STATE = cr_successor.STATE.parent / "cutover-cr"
cutover.OPERATION = "59e26a0e-c144-479b-ba78-b8cba414b006"
cutover.PREFIX = "a0v-qyh-clean-generation-cr-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 281
_target = cutover.target


def _cr_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cr_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CR_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cr_successor.setup()), ensure_ascii=False, indent=2, default=str))
