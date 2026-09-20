#!/usr/bin/env python3
"""Exact internal BG cutover from BF-detached group173."""
from __future__ import annotations

import argparse
import json

import a0v_bg_successor_business as bg_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bg_successor
cutover.STATE = bg_successor.STATE.parent / "cutover-bg"
cutover.OPERATION = "a7928a35-652a-4eaf-8858-d6d86ba7cabe"
cutover.PREFIX = "a0v-qyh-clean-generation-bg-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 173


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BG_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bg_successor.setup()), ensure_ascii=False, indent=2, default=str))
