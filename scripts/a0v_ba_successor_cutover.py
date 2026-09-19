#!/usr/bin/env python3
"""Exact internal BA cutover from AZ-detached group155."""
from __future__ import annotations

import argparse
import json

import a0v_ba_successor_business as ba_successor
import a0v_av_successor_cutover as cutover


cutover.successor = ba_successor
cutover.STATE = ba_successor.STATE.parent / "cutover-ba"
cutover.OPERATION = "c9f78abb-2df1-450e-be02-11ae0bcc7fcf"
cutover.PREFIX = "a0v-qyh-clean-generation-ba-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 155


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BA_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ba_successor.setup()), ensure_ascii=False, indent=2, default=str))
