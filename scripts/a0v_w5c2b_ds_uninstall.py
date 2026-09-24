#!/usr/bin/env python3
"""New-key DS uninstall using the recovered original installation role."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path

import a0v_w5c2a_ds_uninstall as prior
import a0v_w5c2b_identity_recovery as identity

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c2b-ds-uninstall")
KEY = "a0v-w5c2b-ds-uninstall-20260924-v1"


@contextmanager
def _configured():
    old_state, old_key, old_current = prior.STATE, prior.KEY, prior.ds._current
    def current_with_identity():
        current = old_current()
        current._installation_connection = identity.installation_connection
        return current
    prior.STATE, prior.KEY, prior.ds._current = STATE, KEY, current_with_identity
    try:
        yield
    finally:
        prior.STATE, prior.KEY, prior.ds._current = old_state, old_key, old_current


def preflight():
    identity.verify()
    with _configured():
        return prior.preflight()


def uninstall():
    identity.verify()
    with _configured():
        return prior.uninstall()


def audit():
    with _configured():
        return prior.audit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "uninstall", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
