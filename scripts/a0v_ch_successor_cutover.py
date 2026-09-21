#!/usr/bin/env python3
"""Exact internal CH cutover from CG-detached group251."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_ch_successor_business as ch_successor

cutover.successor = ch_successor
cutover.STATE = ch_successor.STATE.parent / "cutover-ch"
cutover.OPERATION = "c0f54fd5-dcc3-4c4e-873c-e06518620b2b"
cutover.PREFIX = "a0v-qyh-clean-generation-ch-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 251
_target = cutover.target


def _ch_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _ch_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CH_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ch_successor.setup()), ensure_ascii=False, indent=2, default=str))
