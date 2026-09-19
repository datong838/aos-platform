#!/usr/bin/env python3
"""Exact internal BB cutover from BA-detached group158."""
from __future__ import annotations

import argparse
import json

import a0v_bb_successor_business as bb_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bb_successor
cutover.STATE = bb_successor.STATE.parent / "cutover-bb"
cutover.OPERATION = "8542118b-56fb-48f5-852f-5a933a38bdee"
cutover.PREFIX = "a0v-qyh-clean-generation-bb-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 158


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BB_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bb_successor.setup()), ensure_ascii=False, indent=2, default=str))
