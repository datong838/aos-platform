#!/usr/bin/env python3
"""Exact internal BI cutover from BH-detached group179."""
from __future__ import annotations

import argparse
import json

import a0v_bi_successor_business as bi_successor
import a0v_av_successor_cutover as cutover


cutover.successor = bi_successor
cutover.STATE = bi_successor.STATE.parent / "cutover-bi"
cutover.OPERATION = "903babc0-58e9-4ae9-b835-6bed4471ba28"
cutover.PREFIX = "a0v-qyh-clean-generation-bi-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 179


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "BI_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, bi_successor.setup()), ensure_ascii=False, indent=2, default=str))
