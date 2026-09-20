#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BL to active BN without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bn_replacement_recovery as bn_replacement
import a0v_bn_successor_business as bn_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight


recovery.STATE = recovery.snapshot.STATE.parent / "bn-saved-snapshot-recovery-v1"
recovery.replacement = bn_replacement.replacement
recovery.successor = bn_successor
recovery.INSTALLATION_LABEL = "BN"
recovery.PREDECESSOR_INSTALLATION_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"
recovery.PREDECESSOR_DEFINITION_REVISION = 118
recovery.TRANSFERRED_DEFINITION_REVISION = 119
recovery.RECOVERY_REVISION = 39
recovery.ENABLED_DEFINITION_REVISION = 120
recovery.PAUSED_DEFINITION_REVISION = 121
recovery.PREDECESSOR_RECOVERY_STATE = "bl-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bn-snapshot"
recovery.DISABLE_KEY = "a0v-bn-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bn-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bn-saved-input-recovery-v39"
recovery.PAUSE_KEY = "a0v-bn-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {
    "FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"
}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = bn_replacement.CREDENTIALS
product_api.BUNDLE_ROOT = bn_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = bn_replacement.TRUST_STATE / "signing/trust-roots.json"

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bn_attempt_guard as guard
    return guard


def _setup():
    return None, None, bn_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup


if __name__ == "__main__":
    recovery.main()
