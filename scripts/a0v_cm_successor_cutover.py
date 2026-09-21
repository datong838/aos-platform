#!/usr/bin/env python3
"""Exact internal CM cutover from CL-detached group266."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cm_successor_business as cm_successor

cutover.successor = cm_successor
cutover.STATE = cm_successor.STATE.parent / "cutover-cm"
cutover.OPERATION = "d6900aae-ce9e-4334-b440-6a337de63dbc"
cutover.PREFIX = "a0v-qyh-clean-generation-cm-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 266
_target = cutover.target


def _cm_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cm_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CM_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cm_successor.setup()), ensure_ascii=False, indent=2, default=str))
