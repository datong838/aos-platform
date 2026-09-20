#!/usr/bin/env python3
"""Exact internal BZ cutover from BY-detached group227."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_bz_successor_business as bz_successor


cutover.successor = bz_successor
cutover.STATE = bz_successor.STATE.parent / "cutover-bz"
cutover.OPERATION = "76130027-8f29-4eaf-bd2f-ca21863b13e1"
cutover.PREFIX = "a0v-qyh-clean-generation-bz-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 227
_target = cutover.target


def _bz_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bz_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BZ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bz_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
