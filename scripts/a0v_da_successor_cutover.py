#!/usr/bin/env python3
"""Exact internal DA cutover from CZ-detached group308."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_da_successor_business as da_successor

cutover.successor = da_successor
cutover.STATE = da_successor.STATE.parent / "cutover-da"
cutover.OPERATION = "96e377b4-e6a2-4a2b-be35-9e8a3fa054ce"
cutover.PREFIX = "a0v-qyh-clean-generation-da-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 308
_target = cutover.target


def _da_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _da_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DA_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, da_successor.setup()), ensure_ascii=False, indent=2, default=str))
