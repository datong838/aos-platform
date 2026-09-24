#!/usr/bin/env python3
"""New-key stage after the old JSON/tuple pre-write rejection."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path

import a0v_w5c3k_current_config_stage as prior

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3kr-config-stage")
KEY = "a0v-w5c3kr-json-tuple-stage-20260924-v1"


@contextmanager
def _configured():
    old_state, old_key = prior.STATE, prior.KEY
    prior.STATE, prior.KEY = STATE, KEY
    try:
        yield
    finally:
        prior.STATE, prior.KEY = old_state, old_key


def _old_key_count():
    with prior.database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        return conn.execute("""SELECT count(*) AS n FROM extension_runtime_configuration
          WHERE org_id='org-org' AND project_id='dev-project'
          AND idempotency_key='a0v-w5c3k-current-four-source-stage-20260924-v1'""").fetchone()["n"]


def preflight():
    if _old_key_count() != 0:
        raise ValueError("W5C3KR_OLD_KEY_COMMITTED_RECONCILE_ONLY")
    with _configured():
        result = prior.preflight()
    return {**result, "outcome": "W5C3KR_STAGE_PREFLIGHT_GREEN"}


def stage():
    preflight()
    with _configured():
        result = prior.stage()
    return {**result, "outcome": "W5C3KR_CONFIG_STAGED"}


def audit():
    if _old_key_count() != 0:
        raise ValueError("W5C3KR_OLD_KEY_COMMITTED_RECONCILE_ONLY")
    with _configured():
        result = prior.audit()
    return {**result, "outcome": "W5C3KR_CURRENT_CONFIG_REV1_STAGED_GREEN"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "stage", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
