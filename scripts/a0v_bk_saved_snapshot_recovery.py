#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BJ to active BK without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bk_replacement_recovery as bk_replacement
import a0v_bk_successor_business as bk_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bk-saved-snapshot-recovery-v1"
recovery.replacement = bk_replacement.replacement
recovery.successor = bk_successor
recovery.INSTALLATION_LABEL = "BK"
recovery.PREDECESSOR_INSTALLATION_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"
recovery.PREDECESSOR_DEFINITION_REVISION = 112
recovery.TRANSFERRED_DEFINITION_REVISION = 113
recovery.RECOVERY_REVISION = 37
recovery.ENABLED_DEFINITION_REVISION = 114
recovery.PAUSED_DEFINITION_REVISION = 115
recovery.PREDECESSOR_RECOVERY_STATE = "bj-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bk-snapshot"
recovery.DISABLE_KEY = "a0v-bk-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bk-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bk-saved-input-recovery-v37"
recovery.PAUSE_KEY = "a0v-bk-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bk_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
