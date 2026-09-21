#!/usr/bin/env python3
"""Exact internal CI cutover from CH-detached group254."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_ci_successor_business as ci_successor

cutover.successor = ci_successor
cutover.STATE = ci_successor.STATE.parent / "cutover-ci"
cutover.OPERATION = "92bdd589-90d4-4e66-817d-1cb05ebfbd1d"
cutover.PREFIX = "a0v-qyh-clean-generation-ci-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 254
_target = cutover.target


def _ci_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _ci_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CI_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ci_successor.setup()), ensure_ascii=False, indent=2, default=str))
