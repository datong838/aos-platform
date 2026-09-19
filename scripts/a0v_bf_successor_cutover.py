#!/usr/bin/env python3
"""Exact internal BF cutover from BE-detached group170."""
from __future__ import annotations

import argparse
import json

import a0v_bf_successor_business as bf_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bf_successor
cutover.STATE = bf_successor.STATE.parent / "cutover-bf"
cutover.OPERATION = "fba548a4-b69d-4ce2-abfc-65abfac41147"
cutover.PREFIX = "a0v-qyh-clean-generation-bf-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 170


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BF_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bf_successor.setup()), ensure_ascii=False, indent=2, default=str))
