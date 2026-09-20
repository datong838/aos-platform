#!/usr/bin/env python3
"""Exact internal BS cutover from BR-detached group206."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_bs_successor_business as bs_successor


cutover.successor = bs_successor
cutover.STATE = bs_successor.STATE.parent / "cutover-bs"
cutover.OPERATION = "b193f4ac-449b-494b-a401-800d5699ce59"
cutover.PREFIX = "a0v-qyh-clean-generation-bs-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 206
_target = cutover.target


def _bs_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bs_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BS_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bs_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
