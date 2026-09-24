#!/usr/bin/env python3
"""Formally retire the second failed approved installation with a new exact key."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path

import a0v_w5c3c_retire_failed_installation as prior
import a0v_w5c3d_clean_successor as clean

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3f-failed-retirement")
KEY = "a0v-w5c3f-retire-failed-prepare-20260924-v1"
OPERATION = "97d921ed-579b-463e-ba2b-0cfccc9d8fb6"


@contextmanager
def _configured():
    old_state, old_key, old_operation, old_load = (
        prior.STATE, prior.KEY, prior.OPERATION, prior.successor._load)
    prior.STATE, prior.KEY, prior.OPERATION = STATE, KEY, OPERATION
    prior.successor._load = clean._load
    try:
        yield
    finally:
        prior.STATE, prior.KEY, prior.OPERATION = old_state, old_key, old_operation
        prior.successor._load = old_load


def preflight():
    with _configured():
        result = prior.preflight()
    if result["installationId"] != clean._load("result")["installationId"]:
        raise ValueError("W5C3F_INSTALLATION_DRIFT")
    return {**result, "outcome": "W5C3F_RETIRE_PREFLIGHT_GREEN"}


def retire():
    preflight()
    with _configured():
        result = prior.retire()
    return {**result, "outcome": "W5C3F_RETIRE_RETURNED"}


def audit():
    with _configured():
        result = prior.audit()
    if result["installationId"] != clean._load("result")["installationId"]:
        raise ValueError("W5C3F_RETIRE_AUDIT_DRIFT")
    return {**result, "outcome": "W5C3F_FAILED_INSTALLATION_RETIRED_GREEN"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "retire", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
