#!/usr/bin/env python3
"""Exact internal CV cutover from CU-detached group293."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cv_successor_business as cv_successor

cutover.successor = cv_successor
cutover.STATE = cv_successor.STATE.parent / "cutover-cv"
cutover.OPERATION = "f340ca4e-3cfd-43e7-ad7b-5b548dcf3bc8"
cutover.PREFIX = "a0v-qyh-clean-generation-cv-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 293
_target = cutover.target


def _cv_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _cv_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CV_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cv_successor.setup()), ensure_ascii=False, indent=2, default=str))
