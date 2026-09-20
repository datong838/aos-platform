#!/usr/bin/env python3
"""Exact internal BV cutover from BU-detached group215."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_bv_successor_business as bv_successor


cutover.successor = bv_successor
cutover.STATE = bv_successor.STATE.parent / "cutover-bv"
cutover.OPERATION = "e8ab9b59-d00e-43d5-9eef-2e3e0da06a37"
cutover.PREFIX = "a0v-qyh-clean-generation-bv-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 215
_target = cutover.target


def _bv_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bv_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BV_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bv_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
