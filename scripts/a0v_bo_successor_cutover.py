#!/usr/bin/env python3
"""Exact internal BO cutover from BN-detached group194."""
from __future__ import annotations

import argparse
import json

import a0v_bo_successor_business as bo_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bo_successor
cutover.STATE = bo_successor.STATE.parent / "cutover-bo"
cutover.OPERATION = "66528958-480d-4e5d-a439-5093e51b31d9"
cutover.PREFIX = "a0v-qyh-clean-generation-bo-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 194
_target = cutover.target


def _bo_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bo_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BO_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bo_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
