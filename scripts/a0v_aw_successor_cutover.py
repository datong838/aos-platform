#!/usr/bin/env python3
"""Exact internal AW cutover from AV-detached group146."""
from __future__ import annotations

import argparse
import json

import a0v_aw_successor_business as aw_successor
import a0v_av_successor_cutover as cutover


cutover.successor = aw_successor
cutover.STATE = aw_successor.STATE.parent / "cutover-aw"
cutover.OPERATION = "255d4a17-0ec9-4506-a1a9-f3337103f832"
cutover.PREFIX = "a0v-qyh-clean-generation-aw-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 146


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "AW_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, aw_successor.setup()), ensure_ascii=False, indent=2, default=str))
