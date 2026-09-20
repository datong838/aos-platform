#!/usr/bin/env python3
"""Exact internal BR cutover from BQ-detached group203."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_br_successor_business as br_successor


cutover.successor = br_successor
cutover.STATE = br_successor.STATE.parent / "cutover-br"
cutover.OPERATION = "3d585d56-1d8b-4211-b1d3-dfc06c96b8ca"
cutover.PREFIX = "a0v-qyh-clean-generation-br-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 203
_target = cutover.target


def _br_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _br_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BR_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, br_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
