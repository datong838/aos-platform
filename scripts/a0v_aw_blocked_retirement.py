#!/usr/bin/env python3
"""Detach configuration-blocked AW through the existing exact disable owner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_as_failed_retirement as retirement


ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ax/retire-aw"
retirement.AS_ID = "f94b9425-9bc4-4369-8ae3-138c50c9ab81"
retirement.GENERATION = "a92f7bb2-3d90-4d88-9632-5fc9a70bd650"
retirement.LOCK = "sha256:f5e2bc370faaaecfc61498af1eac856ba6e4f17c77e6df84aded0bc0ade8ccd3"
retirement.PREFIX = "a0v-qyh-blocked-aw-retirement-20260919-v1"
retirement.FAILED_ATTEMPTS = ()
retirement.INSTALLATION_LABEL = "AW"
retirement.SUCCESSOR_MODULE = "a0v_aw_successor_business"
retirement.ACTIVE_BINDING_REVISION = 9
retirement.ACTIVE_EXECUTION_EPOCH = 5
retirement.ACTIVE_ROUTE_EXECUTION_EPOCH = 3
retirement.DETACHED_BINDING_REVISION = 11
retirement.DETACHED_EXECUTION_EPOCH = 6
retirement.DEFINITION_REVISION = 76
retirement.ACTIVE_ROUTE_REVISION = 120
retirement.ACTIVE_GROUP_REVISION = 147
retirement.DETACHED_ROUTE_REVISION = 122
retirement.DETACHED_GROUP_REVISION = 149


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(retirement.run(args.action), ensure_ascii=False, default=str, indent=2))
