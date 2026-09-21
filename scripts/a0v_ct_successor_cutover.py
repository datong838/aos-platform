#!/usr/bin/env python3
"""Exact internal CT cutover from CS-detached group287."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_ct_successor_business as ct_successor

cutover.successor = ct_successor
cutover.STATE = ct_successor.STATE.parent / "cutover-ct"
cutover.OPERATION = "057d41ab-6558-4946-b677-30152ed7046b"
cutover.PREFIX = "a0v-qyh-clean-generation-ct-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 287
_target = cutover.target


def _ct_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _ct_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CT_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ct_successor.setup()), ensure_ascii=False, indent=2, default=str))
