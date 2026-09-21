#!/usr/bin/env python3
"""Exact internal CL cutover from CK-detached group263."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cl_successor_business as cl_successor

cutover.successor = cl_successor
cutover.STATE = cl_successor.STATE.parent / "cutover-cl"
cutover.OPERATION = "e381a022-f80b-4d45-9e98-91a51077213e"
cutover.PREFIX = "a0v-qyh-clean-generation-cl-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 263
_target = cutover.target


def _cl_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cl_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CL_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cl_successor.setup()), ensure_ascii=False, indent=2, default=str))
