#!/usr/bin/env python3
"""Exact internal BW cutover from BV-detached group218."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_bw_successor_business as bw_successor


cutover.successor = bw_successor
cutover.STATE = bw_successor.STATE.parent / "cutover-bw"
cutover.OPERATION = "8fb2907d-0142-409d-b725-19aa53487f3d"
cutover.PREFIX = "a0v-qyh-clean-generation-bw-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 218
_target = cutover.target


def _bw_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bw_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BW_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bw_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
