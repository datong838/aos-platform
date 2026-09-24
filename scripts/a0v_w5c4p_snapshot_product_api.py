#!/usr/bin/env python3
"""Restore one independent snapshot worker under the exact W5c4p lease."""

from __future__ import annotations

import os
from pathlib import Path

TASK = "A0V-W5C4P-SNAPSHOT-WORKER-20260924"
os.environ["AOS_CONTROLLED_API_LEASE_TASK"] = TASK

import a0v_event_complete_product_api as product_api  # noqa: E402

_original_load_launcher = product_api.load_launcher
_base = Path(__file__).resolve().parents[2] / ".aos-recovery-20260920/state/q-advisor-baseline"


def _current_launcher():
    launcher = _original_load_launcher()
    launcher.DEFAULT_CREDENTIALS = _base / "bm-runtime-credentials/runtime-host-identities.json"
    launcher.BUNDLE_ROOT = _base / "bn-canonical-alias-registry/signed-bundles"
    launcher.TRUST_ROOTS = _base / "bm-trust-root-rotation/signing/trust-roots.json"
    return launcher


product_api.load_launcher = _current_launcher

import a0v_snapshot_product_api as worker  # noqa: E402

worker.STATE = (worker.ROOT.parent / ".aos-recovery-20260920/state/"
                "q-advisor-baseline/20260924-w5c4p-snapshot-worker")
worker.TASK = TASK


if __name__ == "__main__":
    worker.main()
