#!/usr/bin/env python3
"""Exact internal DN cutover from DM-detached group347."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_dn_successor_business as dn_successor

cutover.successor = dn_successor
cutover.STATE = dn_successor.STATE.parent / "cutover-dn"
cutover.OPERATION = "9510cc3c-a547-4d91-881d-34fc7ca18527"
cutover.PREFIX = "a0v-qyh-clean-generation-dn-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 347
_target = cutover.target


def _dn_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _dn_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DN_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, dn_successor.setup()), ensure_ascii=False, indent=2, default=str))
