#!/usr/bin/env python3
"""Exact internal DB cutover from DA-detached group311."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_db_successor_business as db_successor

cutover.successor = db_successor
cutover.STATE = db_successor.STATE.parent / "cutover-db"
cutover.OPERATION = "a717c268-9025-4cd7-b635-0d65fec05e3c"
cutover.PREFIX = "a0v-qyh-clean-generation-db-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 311
_target = cutover.target


def _db_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _db_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DB_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, db_successor.setup()), ensure_ascii=False, indent=2, default=str))
