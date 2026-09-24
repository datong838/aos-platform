#!/usr/bin/env python3
"""Verify the existing third successor PreparedJob once via the original Owner."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json

import a0v_w5c3i_third_natural_prepare as prepared

KEY = "a0v-w5c3j-third-successor-verify-20260924-v1"


@contextmanager
def _configured():
    with prepared._configured():
        old_keys = prepared.prior.KEYS
        prepared.prior.KEYS = {"prepare": prepared.KEY, "verify": KEY}
        try:
            yield
        finally:
            prepared.prior.KEYS = old_keys


def preflight():
    with _configured():
        value = prepared.prior.preflight_verify()
    with prepared.prior.database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        commands = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*prepared.prior.ds.SCOPE.values(), KEY)).fetchone()["n"]
        operations = conn.execute("""SELECT count(*) AS n FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*prepared.prior.ds.SCOPE.values(), KEY)).fetchone()["n"]
    if commands or operations:
        raise ValueError("W5C3J_VERIFY_KEY_ALREADY_USED")
    return {**value, "outcome": "W5C3J_VERIFY_PREFLIGHT_GREEN"}


def request():
    preflight()
    with _configured():
        result = prepared.prior.request_verify()
    if result["replayed"] is not False:
        raise ValueError("W5C3J_VERIFY_REPLAYED_RECONCILE_ONLY")
    return {"outcome": "W5C3J_VERIFY_ACCEPTED", "receipt": result["receipt"]}


def observe():
    with _configured():
        return prepared.prior.observe_verify()


def audit():
    with _configured():
        result = prepared.prior.audit()
    return {**result, "outcome": "W5C3J_ACTIVE_FENCED_GREEN"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "request", "observe", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
