#!/usr/bin/env python3
"""Approve one third clean successor after both failed predecessors are retired."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path

import a0v_w5b_ds_settlement as ds
import a0v_w5c3d_clean_successor as prior
import a0v_w5c3f_retire_failed_installation as second
from a0v_formal_text_model_renewal import database_connect

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3h-third-clean-successor")
PREFIX = "a0v-w5c3h-third-clean-successor-20260924-v1"


@contextmanager
def _configured():
    old_state, old_prefix = prior.STATE, prior.PREFIX
    prior.STATE, prior.PREFIX = STATE, PREFIX
    try:
        yield
    finally:
        prior.STATE, prior.PREFIX = old_state, old_prefix


def _second_retired():
    installation_id = second.clean._load("result")["installationId"]
    value = ds._current().observe_installation(installation_id)
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = conn.execute("""SELECT active_revision FROM bundle_installation
          WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
          (*ds.SCOPE.values(), installation_id)).fetchone()
        attempts = conn.execute("""SELECT count(*) AS n FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
          (*ds.SCOPE.values(), installation_id)).fetchone()["n"]
    if (value["head"]["state"] != "uninstalled"
            or value["head"]["etag_version"] != 4
            or head is None or head["active_revision"] is not None
            or value["bindings"] or len(value["operations"]) != 1
            or str(value["operations"][0]["operation_id"]) != second.OPERATION
            or value["operations"][0]["status"] != "failed"
            or len(value["resources"]) != 3
            or any(r["cleanup_state"] != "released" or r["observed_release"] is not True
                   for r in value["resources"])
            or attempts != 0 or value["canaryInstallations"] != 0):
        raise ValueError("W5C3H_SECOND_PREDECESSOR_DRIFT")
    return installation_id


def preflight():
    second_id = _second_retired()
    with _configured():
        result = prior.preflight()
    return {**result, "outcome": "W5C3H_PREFLIGHT_GREEN",
            "secondRetiredId": second_id}


def approve():
    preflight()
    with _configured():
        result = prior.approve()
    return {**result, "outcome": "W5C3H_APPROVAL_RETURNED"}


def audit():
    second_id = _second_retired()
    with _configured():
        result = prior.audit()
    return {**result, "outcome": "W5C3H_THIRD_SUCCESSOR_APPROVED_GREEN",
            "secondRetiredId": second_id}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "approve", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
