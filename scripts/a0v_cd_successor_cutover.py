#!/usr/bin/env python3
"""Exact internal CD cutover from CC-detached group239."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_cd_successor_business as cd_successor

cutover.successor = cd_successor
cutover.STATE = cd_successor.STATE.parent / "cutover-cd"
cutover.OPERATION = "71d85398-64db-4cfe-8df6-b5f83fdc7ebb"
cutover.PREFIX = "a0v-qyh-clean-generation-cd-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 239
_target = cutover.target
def _cd_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})
cutover.target = _cd_target
def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CD_")}
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, cd_successor.setup()), ensure_ascii=False, indent=2, default=str))
