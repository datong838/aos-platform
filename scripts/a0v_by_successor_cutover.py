#!/usr/bin/env python3
"""Exact internal BY cutover from BX-detached group224."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_by_successor_business as by_successor


cutover.successor = by_successor
cutover.STATE = by_successor.STATE.parent / "cutover-by"
cutover.OPERATION = "335da3b8-6101-4f42-9235-0623b9dda80c"
cutover.PREFIX = "a0v-qyh-clean-generation-by-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 224
_target = cutover.target


def _by_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _by_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BY_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, by_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
