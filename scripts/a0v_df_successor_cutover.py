#!/usr/bin/env python3
"""Exact internal DF cutover from DE-detached group323."""
from __future__ import annotations
import argparse
import json
import a0v_av_successor_cutover as cutover
import a0v_df_successor_business as df_successor

cutover.successor = df_successor
cutover.STATE = df_successor.STATE.parent / "cutover-df"
cutover.OPERATION = "579e9602-9686-4fba-bd44-8742119e9074"
cutover.PREFIX = "a0v-qyh-clean-generation-df-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 323
_target = cutover.target


def _df_target(registration):
    return _target({**registration, "outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"})


cutover.target = _df_target


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DF_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, df_successor.setup()), ensure_ascii=False, indent=2, default=str))
