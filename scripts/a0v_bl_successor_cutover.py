#!/usr/bin/env python3
"""Exact internal BL cutover from BK-detached group188."""
from __future__ import annotations

import argparse
import json

import a0v_bl_successor_business as bl_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bl_successor
cutover.STATE = bl_successor.STATE.parent / "cutover-bl"
cutover.OPERATION = "7acaa1be-bfe3-481b-9841-c4b09779b4f8"
cutover.PREFIX = "a0v-qyh-clean-generation-bl-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 188


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BL_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bl_successor.setup()), ensure_ascii=False, indent=2, default=str))
