#!/usr/bin/env python3
"""Exact internal CN cutover from CM-detached group269."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cn_successor_business as cn_successor

cutover.successor = cn_successor
cutover.STATE = cn_successor.STATE.parent / "cutover-cn"
cutover.OPERATION = "abfafc4b-9a00-433e-af6c-54636f8e5983"
cutover.PREFIX = "a0v-qyh-clean-generation-cn-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 269
_target = cutover.target


def _cn_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cn_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CN_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cn_successor.setup()), ensure_ascii=False, indent=2, default=str))
