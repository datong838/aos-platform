#!/usr/bin/env python3
"""Exact internal BP cutover from BO-detached group197."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_bp_successor_business as bp_successor


cutover.successor = bp_successor
cutover.STATE = bp_successor.STATE.parent / "cutover-bp"
cutover.OPERATION = "46da254e-6842-4a33-9540-e6a47065a65a"
cutover.PREFIX = "a0v-qyh-clean-generation-bp-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 197
_target = cutover.target


def _bp_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bp_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BP_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bp_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
