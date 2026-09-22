#!/usr/bin/env python3
"""Exact internal DO cutover from DN-detached group350."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_do_successor_business as do_successor

cutover.successor = do_successor
cutover.STATE = do_successor.STATE.parent / "cutover-do"
cutover.OPERATION = "9269e6d0-0052-45f7-9f5f-24cb5f62e2b4"
cutover.PREFIX = "a0v-qyh-clean-generation-do-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 350
_target = cutover.target


def _do_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _do_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DO_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, do_successor.setup()), ensure_ascii=False, indent=2, default=str))
