#!/usr/bin/env python3
"""Exact internal CJ cutover from CI-detached group257."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cj_successor_business as cj_successor

cutover.successor = cj_successor
cutover.STATE = cj_successor.STATE.parent / "cutover-cj"
cutover.OPERATION = "82b2884f-7625-47d5-a531-ea32c9ed6f14"
cutover.PREFIX = "a0v-qyh-clean-generation-cj-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 257
_target = cutover.target


def _cj_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cj_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CJ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cj_successor.setup()), ensure_ascii=False, indent=2, default=str))
