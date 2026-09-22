#!/usr/bin/env python3
"""Exact internal DG cutover from DF-detached group326."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dg_successor_business as dg_successor

cutover.successor = dg_successor
cutover.STATE = dg_successor.STATE.parent / "cutover-dg"
cutover.OPERATION = "0c292cdc-7cbb-4e9b-8d9b-a5493ea1fbe3"
cutover.PREFIX = "a0v-qyh-clean-generation-dg-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 326
_target = cutover.target


def _dg_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dg_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DG_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dg_successor.setup()), ensure_ascii=False, indent=2, default=str))
