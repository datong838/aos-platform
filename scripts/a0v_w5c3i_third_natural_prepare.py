#!/usr/bin/env python3
"""One naturally consumed apply for the third clean successor."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path

import a0v_w5c3b_successor_lifecycle as prior
import a0v_w5c3h_third_clean_successor as third

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3i-third-natural-prepare")
KEY = "a0v-w5c3i-third-successor-prepare-20260924-v1"


@contextmanager
def _configured():
    old_state, old_keys, old_load = prior.STATE, prior.KEYS, prior.successor._load
    prior.STATE = STATE
    prior.KEYS = {"prepare": KEY, "verify": "w5c3i-verify-not-authorized"}
    prior.successor._load = third.prior._load
    old_third_state = third.prior.STATE
    third.prior.STATE = third.STATE
    try:
        yield
    finally:
        third.prior.STATE = old_third_state
        prior.STATE, prior.KEYS, prior.successor._load = old_state, old_keys, old_load


def _result():
    with third._configured():
        return third.prior._load("result")


def preflight():
    third.audit()
    with _configured():
        value = prior.preflight_prepare()
    if value["installationId"] != _result()["installationId"]:
        raise ValueError("W5C3I_INSTALLATION_DRIFT")
    with prior.database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        commands = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*prior.ds.SCOPE.values(), KEY)).fetchone()["n"]
        operations = conn.execute("""SELECT count(*) AS n FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*prior.ds.SCOPE.values(), KEY)).fetchone()["n"]
    if commands or operations:
        raise ValueError("W5C3I_KEY_ALREADY_USED")
    return {**value, "outcome": "W5C3I_PREFLIGHT_GREEN"}


def request():
    preflight()
    with _configured():
        result = prior.request_prepare()
    if result["replayed"] is not False:
        raise ValueError("W5C3I_REQUEST_REPLAYED_RECONCILE_ONLY")
    return {"outcome": "W5C3I_PREPARE_ACCEPTED", "receipt": result["receipt"]}


def observe():
    with _configured():
        return prior.observe_prepare()


def audit():
    with _configured():
        result = prior.preflight_verify()
        observed = prior.observe_prepare()
    if observed["operation"]["status"] != "succeeded":
        raise ValueError("W5C3I_PREPARE_NOT_TERMINAL_SUCCESS")
    return {"outcome": "W5C3I_LIVE_PREPARED_JOB_GREEN",
            "installationId": result["installationId"],
            "generation": result["generation"], "hostPid": result["hostPid"],
            "resources": observed["resources"], "etag": 4}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "request", "observe", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
