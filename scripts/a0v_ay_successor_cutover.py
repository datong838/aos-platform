#!/usr/bin/env python3
"""Exact internal AY cutover from AX-detached group152."""
from __future__ import annotations

import argparse
import json

import a0v_ay_successor_business as ay_successor
import a0v_av_successor_cutover as cutover


cutover.successor = ay_successor
cutover.STATE = ay_successor.STATE.parent / "cutover-ay"
cutover.OPERATION = "98a056c1-bba0-4073-bda1-0fa16d214f10"
cutover.PREFIX = "a0v-qyh-clean-generation-ay-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 152


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "AY_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ay_successor.setup()), ensure_ascii=False, indent=2, default=str))
