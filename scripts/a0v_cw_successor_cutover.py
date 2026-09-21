#!/usr/bin/env python3
"""Exact internal CW cutover from CV-detached group296."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cw_successor_business as cw_successor

cutover.successor = cw_successor
cutover.STATE = cw_successor.STATE.parent / "cutover-cw"
cutover.OPERATION = "502876a9-ba7c-439d-83ad-e1124cc7e231"
cutover.PREFIX = "a0v-qyh-clean-generation-cw-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 296
_target = cutover.target


def _cw_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cw_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CW_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cw_successor.setup()), ensure_ascii=False, indent=2, default=str))
