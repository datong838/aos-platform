#!/usr/bin/env python3
"""Use the existing AIP approval Owner against the scoped head database."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3p_cutover_approval as prior
import a0v_w5c3pr_approval_permission_inventory as recovery
import a0v_qyh_current_product_event_first_chain as aip

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3s-cutover-approval-recovery")
KEY = "a0v-w5c3s-third-successor-cutover-approval-20260924-v1"


@contextmanager
def _configured():
    old_state, old_key, old_connect = prior.STATE, prior.KEY, aip._web_connection
    prior.STATE, prior.KEY, aip._web_connection = STATE, KEY, recovery.head_action_connection
    try:
        yield
    finally:
        prior.STATE, prior.KEY, aip._web_connection = old_state, old_key, old_connect


def _new_key_count():
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        return conn.execute("""SELECT count(*) AS n FROM aip_action_proposal
          WHERE org_id='org-org' AND project_id='dev-project'
          AND idempotency_key=%s""", (KEY + ":proposal",)).fetchone()["n"]


def preflight():
    old = prior.reconcile()
    if old["outcome"] != "W5C3P_APPROVAL_PREWRITE_REJECTED" or _new_key_count() != 0:
        raise ValueError("W5C3S_OLD_OR_NEW_BOUNDARY_DRIFT")
    permissions = recovery.inventory()
    if (permissions["scopedHeadConnection"]["role_name"] != "aos_runtime"
            or permissions["scopedHeadConnection"]["cutover_action_types"] != 1):
        raise ValueError("W5C3S_APPROVAL_AUTHORITY_DRIFT")
    with _configured():
        value = prior.preflight()
    return {**value, "outcome": "W5C3S_APPROVAL_PREFLIGHT_GREEN",
            "cutoverActionRevisionHash": permissions["cutoverActionRevisionHash"]}


def approve():
    preflight()
    with _configured():
        result = prior.approve()
    return {**result, "outcome": "W5C3S_CUTOVER_APPROVED"}


def audit():
    with _configured():
        result = prior.audit()
    if _new_key_count() != 1:
        raise ValueError("W5C3S_UNIQUE_PROPOSAL_REQUIRED")
    return {**result, "outcome": "W5C3S_APPROVAL_GREEN"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "approve", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
