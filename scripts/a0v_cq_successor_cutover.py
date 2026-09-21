#!/usr/bin/env python3
"""Exact internal CQ cutover from CP-detached group278."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cq_successor_business as cq_successor

cutover.successor = cq_successor
cutover.STATE = cq_successor.STATE.parent / "cutover-cq"
cutover.OPERATION = "ebd2d074-9800-4ccb-9f91-0fed1beda3d1"
cutover.PREFIX = "a0v-qyh-clean-generation-cq-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 278
_target = cutover.target


def _cq_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cq_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CQ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cq_successor.setup()), ensure_ascii=False, indent=2, default=str))
