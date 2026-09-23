#!/usr/bin/env python3
"""Exact internal DS cutover from DR-detached group362."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_w5_ds_successor_business as ds_successor

cutover.successor = ds_successor.successor
cutover.STATE = ds_successor.STATE.parent / "cutover-ds"
cutover.OPERATION = "881ef400-d499-4f7b-b08e-6c1891d6122d"
cutover.PREFIX = "a0v-qyh-clean-generation-ds-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 362
_target = cutover.target


def _ds_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _ds_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DS_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ds_successor.setup()), ensure_ascii=False, indent=2, default=str))
