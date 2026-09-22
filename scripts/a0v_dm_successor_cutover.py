#!/usr/bin/env python3
"""Exact internal DM cutover from DL-detached group344."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dm_successor_business as dm_successor

cutover.successor = dm_successor
cutover.STATE = dm_successor.STATE.parent / "cutover-dm"
cutover.OPERATION = "a8f4e2c1-6b09-4d7a-9e15-3c82f1d047b6"
cutover.PREFIX = "a0v-qyh-clean-generation-dm-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 344
_target = cutover.target


def _dm_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dm_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DM_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dm_successor.setup()), ensure_ascii=False, indent=2, default=str))
