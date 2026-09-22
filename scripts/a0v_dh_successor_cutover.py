#!/usr/bin/env python3
"""Exact internal DH cutover from DG-detached group329."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dh_successor_business as dh_successor

cutover.successor = dh_successor
cutover.STATE = dh_successor.STATE.parent / "cutover-dh"
cutover.OPERATION = "843181a5-c8be-42e4-953a-9500534058a9"
cutover.PREFIX = "a0v-qyh-clean-generation-dh-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 329
_target = cutover.target


def _dh_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dh_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DH_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dh_successor.setup()), ensure_ascii=False, indent=2, default=str))
