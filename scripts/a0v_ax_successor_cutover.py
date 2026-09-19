#!/usr/bin/env python3
"""Exact internal AX cutover from AW-detached group149."""
from __future__ import annotations

import argparse
import json

import a0v_ax_successor_business as ax_successor
import a0v_av_successor_cutover as cutover


cutover.successor = ax_successor
cutover.STATE = ax_successor.STATE.parent / "cutover-ax"
cutover.OPERATION = "900ed51b-9c97-424b-9a19-5e4dc2868f66"
cutover.PREFIX = "a0v-qyh-clean-generation-ax-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 149


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "AX_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ax_successor.setup()), ensure_ascii=False, indent=2, default=str))
