#!/usr/bin/env python3
"""Run the bounded W5c9a HTTP-only profile with current private roots."""

import os
from pathlib import Path

import a0v_product_controlled_api as product


TASK = 'A0V-W5C9A-HTTP-ONLY-20260926'
BASE = Path(__file__).resolve().parents[2] / '.aos-recovery-20260920/state/q-advisor-baseline'


def load_launcher():
    launcher = product.load_launcher()
    launcher.DEFAULT_CREDENTIALS = BASE / 'bm-runtime-credentials/runtime-host-identities.json'
    launcher.TRUST_ROOTS = BASE / 'bm-trust-root-rotation/signing/trust-roots.json'
    launcher.BUNDLE_ROOT = BASE / 'bn-canonical-alias-registry/signed-bundles'
    return launcher


if __name__ == '__main__':
    os.environ['AOS_CONTROLLED_API_LEASE_TASK'] = TASK
    load_launcher().main()
