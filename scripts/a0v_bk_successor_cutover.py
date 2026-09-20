#!/usr/bin/env python3
"""Exact internal BK cutover from BJ-detached group185."""
from __future__ import annotations

import argparse
import json

import a0v_bk_successor_business as bk_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bk_successor
cutover.STATE = bk_successor.STATE.parent / "cutover-bk"
cutover.OPERATION = "30355379-f48e-4261-91cc-533f13c34ab6"
cutover.PREFIX = "a0v-qyh-clean-generation-bk-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 185


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BK_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bk_successor.setup()), ensure_ascii=False, indent=2, default=str))
