#!/usr/bin/env python3
"""Exact internal DJ cutover from DI-detached group335."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dj_successor_business as dj_successor

cutover.successor = dj_successor
cutover.STATE = dj_successor.STATE.parent / "cutover-dj"
cutover.OPERATION = "af5b251d-5a47-46c2-a651-866fe0c05018"
cutover.PREFIX = "a0v-qyh-clean-generation-dj-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 335
_target = cutover.target


def _dj_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dj_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DJ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dj_successor.setup()), ensure_ascii=False, indent=2, default=str))
