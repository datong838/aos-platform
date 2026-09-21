#!/usr/bin/env python3
"""Exact internal CO cutover from CN-detached group272."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_co_successor_business as co_successor

cutover.successor = co_successor
cutover.STATE = co_successor.STATE.parent / "cutover-co"
cutover.OPERATION = "7e21a322-9f77-4d5b-baa2-f6d7ba19da13"
cutover.PREFIX = "a0v-qyh-clean-generation-co-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 272
_target = cutover.target


def _co_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _co_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CO_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, co_successor.setup()), ensure_ascii=False, indent=2, default=str))
