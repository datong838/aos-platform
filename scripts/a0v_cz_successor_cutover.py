#!/usr/bin/env python3
"""Exact internal CZ cutover from CY-detached group305."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cz_successor_business as cz_successor

cutover.successor = cz_successor
cutover.STATE = cz_successor.STATE.parent / "cutover-cz"
cutover.OPERATION = "3b1ab629-3d48-4ae0-b685-f0dca64ae8cc"
cutover.PREFIX = "a0v-qyh-clean-generation-cz-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 305
_target = cutover.target


def _cz_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cz_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CZ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cz_successor.setup()), ensure_ascii=False, indent=2, default=str))
