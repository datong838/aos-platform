#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BG to active BH without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bh_replacement_recovery as bh_replacement
import a0v_bh_successor_business as bh_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bh-saved-snapshot-recovery-v1"
recovery.replacement = bh_replacement.replacement
recovery.successor = bh_successor
recovery.INSTALLATION_LABEL = "BH"
recovery.PREDECESSOR_INSTALLATION_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"
recovery.PREDECESSOR_DEFINITION_REVISION = 103
recovery.TRANSFERRED_DEFINITION_REVISION = 104
recovery.RECOVERY_REVISION = 34
recovery.ENABLED_DEFINITION_REVISION = 105
recovery.PAUSED_DEFINITION_REVISION = 106
recovery.PREDECESSOR_RECOVERY_STATE = "bg-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bh-snapshot"
recovery.DISABLE_KEY = "a0v-bh-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bh-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bh-saved-input-recovery-v34"
recovery.PAUSE_KEY = "a0v-bh-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bh_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
