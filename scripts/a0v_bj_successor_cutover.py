#!/usr/bin/env python3
"""Exact internal BJ cutover from BI-detached group182."""
from __future__ import annotations

import argparse
import json

import a0v_bj_successor_business as bj_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bj_successor
cutover.STATE = bj_successor.STATE.parent / "cutover-bj"
cutover.OPERATION = "337aa516-42f1-47fc-afb7-980d3c0e62e1"
cutover.PREFIX = "a0v-qyh-clean-generation-bj-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 182


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BJ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bj_successor.setup()), ensure_ascii=False, indent=2, default=str))
