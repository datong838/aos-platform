#!/usr/bin/env python3
"""Exact internal BT cutover from BS-detached group209."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_bt_successor_business as bt_successor


cutover.successor = bt_successor
cutover.STATE = bt_successor.STATE.parent / "cutover-bt"
cutover.OPERATION = "18eda226-e087-4342-bfc6-21def9226112"
cutover.PREFIX = "a0v-qyh-clean-generation-bt-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 209
_target = cutover.target


def _bt_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bt_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BT_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bt_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
