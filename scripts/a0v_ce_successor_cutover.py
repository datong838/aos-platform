#!/usr/bin/env python3
"""Exact internal CE cutover from CD-detached group242."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_ce_successor_business as ce_successor

cutover.successor = ce_successor
cutover.STATE = ce_successor.STATE.parent / "cutover-ce"
cutover.OPERATION = "024169d1-9a17-4530-a745-33aac90053ac"
cutover.PREFIX = "a0v-qyh-clean-generation-ce-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 242
_target = cutover.target
def _ce_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})
cutover.target = _ce_target
def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "CE_")}
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, ce_successor.setup()), ensure_ascii=False, indent=2, default=str))
