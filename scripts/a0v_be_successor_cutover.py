#!/usr/bin/env python3
"""Exact internal BE cutover from BD-detached group167."""
from __future__ import annotations

import argparse
import json

import a0v_be_successor_business as be_successor
import a0v_av_successor_cutover as cutover


cutover.successor = be_successor
cutover.STATE = be_successor.STATE.parent / "cutover-be"
cutover.OPERATION = "7bd8c758-35a8-47ab-8498-22129a474fc7"
cutover.PREFIX = "a0v-qyh-clean-generation-be-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 167


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BE_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, be_successor.setup()), ensure_ascii=False, indent=2, default=str))
