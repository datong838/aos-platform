#!/usr/bin/env python3
"""Exact internal BX cutover from BW-detached group221."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_bx_successor_business as bx_successor


cutover.successor = bx_successor
cutover.STATE = bx_successor.STATE.parent / "cutover-bx"
cutover.OPERATION = "b3c173dc-ea28-41a8-b02c-702ac71ac456"
cutover.PREFIX = "a0v-qyh-clean-generation-bx-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 221
_target = cutover.target


def _bx_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bx_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BX_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bx_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
