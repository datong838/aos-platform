#!/usr/bin/env python3
"""Pure HTTP control API for BV; cron, snapshot worker and in-process host stay disabled."""
from __future__ import annotations

from pathlib import Path
import sys

import a0v_event_complete_product_api as product_api


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
CREDENTIALS = BASE / "bm-runtime-credentials/runtime-host-identities.json"
BUNDLE_ROOT = BASE / "bn-canonical-alias-registry/signed-bundles"
TRUST_ROOTS = BASE / "bm-trust-root-rotation/signing/trust-roots.json"


def load_launcher():
    launcher = product_api.load_launcher()
    launcher.DEFAULT_CREDENTIALS = CREDENTIALS
    launcher.BUNDLE_ROOT = BUNDLE_ROOT
    launcher.TRUST_ROOTS = TRUST_ROOTS
    launcher.API_FLAGS = dict(launcher.API_FLAGS,
        AOS_QYH_CRON_ENABLED="false", AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false",
        AOS_EXTENSION_RUNTIME_HOST_ENABLED="0")
    return launcher


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    load_launcher().main()
