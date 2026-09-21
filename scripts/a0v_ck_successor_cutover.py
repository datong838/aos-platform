#!/usr/bin/env python3
"""Exact internal CK cutover from CJ-detached group260."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_ck_successor_business as ck_successor

cutover.successor = ck_successor
cutover.STATE = ck_successor.STATE.parent / "cutover-ck"
cutover.OPERATION = "4d7f869d-15bd-4246-8f92-7c52e59c7c23"
cutover.PREFIX = "a0v-qyh-clean-generation-ck-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 260
_target = cutover.target


def _ck_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _ck_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CK_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ck_successor.setup()), ensure_ascii=False, indent=2, default=str))
