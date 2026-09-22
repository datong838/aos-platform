#!/usr/bin/env python3
"""Exact internal DE cutover from DD-detached group320."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_de_successor_business as de_successor

cutover.successor = de_successor
cutover.STATE = de_successor.STATE.parent / "cutover-de"
cutover.OPERATION = "2d1c92d1-a525-44a9-b41a-f71b9a9a4bb7"
cutover.PREFIX = "a0v-qyh-clean-generation-de-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 320
_target = cutover.target


def _de_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _de_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DE_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, de_successor.setup()), ensure_ascii=False, indent=2, default=str))
