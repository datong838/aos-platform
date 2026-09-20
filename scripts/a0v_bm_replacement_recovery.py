#!/usr/bin/env python3
"""Create BM directly from the exact detached BL authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
TRUST_STATE = RECOVERY / "bm-trust-root-rotation"
CREDENTIALS = RECOVERY / "bm-runtime-credentials/runtime-host-identities.json"
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bm-activation"
replacement.AV_DIR = replacement.STATE / "bm"
replacement.AU_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"
replacement.AU_GENERATION = "116d12fc-93bc-4071-a973-fdc6830ea8b1"
replacement.LOCK = "sha256:47af46b5658b7952f9d3068466ba06c6203e51fef899c5d661026230893b334e"
replacement.AU_DISABLE_OPERATION = "7e82992b-0f1b-429f-bcda-36d416ff9cdb"
replacement.AU_DETACH_RECEIPT = "3a50db9a-2dec-4543-b37a-701a8e12ee36"
replacement.AU_DETACH_HASH = "sha256:265c6dcf811b6df90e5402fc7f1bc53aad22d8f49d29ec7caffe90f779a40f15"
replacement.PREFIX = "a0v-qyh-clean-bm-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 164
replacement.PREDECESSOR_GROUP_REVISION = 191
replacement.DEFINITION_REVISION = 118
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bm"
replacement.BUNDLE_ROOT = TRUST_STATE / "signed-bundles"
replacement.VERSIONS = {
    "domain.ecommerce.core": "1.4.1",
    "platform.ecommerce.niushop": "1.23.1",
    "solution.ecommerce.growth": "1.10.1",
    "solution.ecommerce.operations-base": "1.2.1",
}


_base_load_profile = replacement.load_profile


def _load_profile():
    profile = _base_load_profile()
    profile.TRUST_STATE = TRUST_STATE
    profile.BUNDLE_ROOT = replacement.BUNDLE_ROOT
    profile.VERSIONS = dict(replacement.VERSIONS)
    original_load = profile._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = CREDENTIALS
        return module

    profile._load = load
    return profile


replacement.load_profile = _load_profile


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BM_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=replacement.ACTIONS)
    args = parser.parse_args()
    output = replacement.STATE / f"{args.action}-result.json"
    if output.exists():
        raise ValueError(f"immutable {args.action} output exists")
    result = run(args.action)
    replacement.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
