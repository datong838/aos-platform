#!/usr/bin/env python3
"""Exact internal BH cutover from BG-detached group176."""
from __future__ import annotations

import argparse
import json

import a0v_bh_successor_business as bh_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bh_successor
cutover.STATE = bh_successor.STATE.parent / "cutover-bh"
cutover.OPERATION = "d21dc573-c75f-47cc-8c9a-e9d2545d5f17"
cutover.PREFIX = "a0v-qyh-clean-generation-bh-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 176


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BH_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bh_successor.setup()), ensure_ascii=False, indent=2, default=str))
