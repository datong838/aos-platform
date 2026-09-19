#!/usr/bin/env python3
"""Exact internal BD cutover from BC-detached group164."""
from __future__ import annotations

import argparse
import json

import a0v_bd_successor_business as bd_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bd_successor
cutover.STATE = bd_successor.STATE.parent / "cutover-bd"
cutover.OPERATION = "e4baf529-cc27-4a0d-aa18-139b22f6dd19"
cutover.PREFIX = "a0v-qyh-clean-generation-bd-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 164


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BD_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bd_successor.setup()), ensure_ascii=False, indent=2, default=str))
