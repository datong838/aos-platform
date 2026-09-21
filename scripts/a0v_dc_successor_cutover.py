#!/usr/bin/env python3
"""Exact internal DC cutover from DB-detached group314."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dc_successor_business as dc_successor

cutover.successor = dc_successor
cutover.STATE = dc_successor.STATE.parent / "cutover-dc"
cutover.OPERATION = "232d8e1e-9efb-4e26-99ce-e83872539a32"
cutover.PREFIX = "a0v-qyh-clean-generation-dc-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 314
_target = cutover.target


def _dc_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dc_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DC_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dc_successor.setup()), ensure_ascii=False, indent=2, default=str))
