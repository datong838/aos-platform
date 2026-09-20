#!/usr/bin/env python3
"""Exact internal BQ cutover from BP-detached group200."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_cutover as cutover
import a0v_bq_successor_business as bq_successor


cutover.successor = bq_successor
cutover.STATE = bq_successor.STATE.parent / "cutover-bq"
cutover.OPERATION = "fc19b7bd-d506-4e85-a528-a3b0ce9e6ff4"
cutover.PREFIX = "a0v-qyh-clean-generation-bq-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 200
_target = cutover.target


def _bq_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _bq_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BQ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit",
                                          "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bq_successor.setup()), ensure_ascii=False,
                     indent=2, default=str))
