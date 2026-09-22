#!/usr/bin/env python3
"""Exact internal DL cutover from DK-detached group341."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dl_successor_business as dl_successor

cutover.successor = dl_successor
cutover.STATE = dl_successor.STATE.parent / "cutover-dl"
cutover.OPERATION = "6d3f1c8b-7092-4d5e-9ac0-23865f729064"
cutover.PREFIX = "a0v-qyh-clean-generation-dl-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 341
_target = cutover.target


def _dl_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dl_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DL_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dl_successor.setup()), ensure_ascii=False, indent=2, default=str))
