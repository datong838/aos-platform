#!/usr/bin/env python3
"""Exact internal CA cutover from BZ-detached group230."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_ca_successor_business as ca_successor


cutover.successor = ca_successor
cutover.STATE = ca_successor.STATE.parent / "cutover-ca"
cutover.OPERATION = "551a9424-2d4c-4d0e-88e1-151bb85effd0"
cutover.PREFIX = "a0v-qyh-clean-generation-ca-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 230
_target = cutover.target


def _ca_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _ca_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CA_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ca_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
