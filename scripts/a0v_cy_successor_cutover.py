#!/usr/bin/env python3
"""Exact internal CY cutover from CX-detached group302."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cy_successor_business as cy_successor

cutover.successor = cy_successor
cutover.STATE = cy_successor.STATE.parent / "cutover-cy"
cutover.OPERATION = "c7c81fae-1803-4c22-a664-49976472c138"
cutover.PREFIX = "a0v-qyh-clean-generation-cy-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 302
_target = cutover.target


def _cy_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cy_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CY_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cy_successor.setup()), ensure_ascii=False, indent=2, default=str))
