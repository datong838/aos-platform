#!/usr/bin/env python3
"""Exact internal BC cutover from BB-detached group161."""
from __future__ import annotations

import argparse
import json

import a0v_bc_successor_business as bc_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bc_successor
cutover.STATE = bc_successor.STATE.parent / "cutover-bc"
cutover.OPERATION = "a2c78a81-eb53-4b13-b390-2b029530313f"
cutover.PREFIX = "a0v-qyh-clean-generation-bc-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 161


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BC_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bc_successor.setup()), ensure_ascii=False, indent=2, default=str))
