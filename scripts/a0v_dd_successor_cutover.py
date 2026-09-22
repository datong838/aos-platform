#!/usr/bin/env python3
"""Exact internal DD cutover from DC-detached group317."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dd_successor_business as dd_successor

cutover.successor = dd_successor
cutover.STATE = dd_successor.STATE.parent / "cutover-dd"
cutover.OPERATION = "a6716200-8b3f-44d5-a2fc-abf423e970d1"
cutover.PREFIX = "a0v-qyh-clean-generation-dd-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 317
_target = cutover.target


def _dd_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dd_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DD_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dd_successor.setup()), ensure_ascii=False, indent=2, default=str))
