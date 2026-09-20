#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BK to active BL without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bl_replacement_recovery as bl_replacement
import a0v_bl_successor_business as bl_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bl-saved-snapshot-recovery-v1"
recovery.replacement = bl_replacement.replacement
recovery.successor = bl_successor
recovery.INSTALLATION_LABEL = "BL"
recovery.PREDECESSOR_INSTALLATION_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"
recovery.PREDECESSOR_DEFINITION_REVISION = 115
recovery.TRANSFERRED_DEFINITION_REVISION = 116
recovery.RECOVERY_REVISION = 38
recovery.ENABLED_DEFINITION_REVISION = 117
recovery.PAUSED_DEFINITION_REVISION = 118
recovery.PREDECESSOR_RECOVERY_STATE = "bk-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bl-snapshot"
recovery.DISABLE_KEY = "a0v-bl-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bl-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bl-saved-input-recovery-v38"
recovery.PAUSE_KEY = "a0v-bl-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bl_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
