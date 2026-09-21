#!/usr/bin/env python3
"""Exact internal CS cutover from CR-detached group284."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cs_successor_business as cs_successor

cutover.successor = cs_successor
cutover.STATE = cs_successor.STATE.parent / "cutover-cs"
cutover.OPERATION = "d4036350-f591-4064-abf2-4e2849115c57"
cutover.PREFIX = "a0v-qyh-clean-generation-cs-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 284
_target = cutover.target


def _cs_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cs_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CS_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cs_successor.setup()), ensure_ascii=False, indent=2, default=str))
