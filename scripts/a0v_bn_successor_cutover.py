#!/usr/bin/env python3
"""Exact internal BN cutover from BL-detached group191."""
from __future__ import annotations

import argparse
import json

import a0v_bn_successor_business as bn_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bn_successor
cutover.STATE = bn_successor.STATE.parent / "cutover-bn"
cutover.OPERATION = "dda42306-073e-4d30-9027-680510925b05"
cutover.PREFIX = "a0v-qyh-clean-generation-bn-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 191
_target = cutover.target


def _bn_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bn_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BN_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bn_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
