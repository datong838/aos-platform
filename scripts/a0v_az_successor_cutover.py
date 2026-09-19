#!/usr/bin/env python3
"""Exact internal AZ cutover from AX-detached group152."""
from __future__ import annotations

import argparse
import json

import a0v_az_successor_business as az_successor
import a0v_av_successor_cutover as cutover


cutover.successor = az_successor
cutover.STATE = az_successor.STATE.parent / "cutover-az"
cutover.OPERATION = "f411835c-ea85-4996-9c64-715e9d04fc35"
cutover.PREFIX = "a0v-qyh-clean-generation-az-cutover-v1"
cutover.PREDECESSOR_GROUP_REVISION = 152


def invoke(phase, plane):
    result = cutover.invoke(phase, plane)
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "AZ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"])
    args = parser.parse_args()
    print(json.dumps(invoke(args.phase, az_successor.setup()), ensure_ascii=False, indent=2, default=str))
