#!/usr/bin/env python3
"""Exact internal DI cutover from DH-detached group332."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_di_successor_business as di_successor

cutover.successor = di_successor
cutover.STATE = di_successor.STATE.parent / "cutover-di"
cutover.OPERATION = "818723c0-2995-441d-9409-dc1530f093e7"
cutover.PREFIX = "a0v-qyh-clean-generation-di-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 332
_target = cutover.target


def _di_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _di_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DI_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, di_successor.setup()), ensure_ascii=False, indent=2, default=str))
