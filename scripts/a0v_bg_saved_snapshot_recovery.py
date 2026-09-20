#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BF to active BG without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bg_replacement_recovery as bg_replacement
import a0v_bg_successor_business as bg_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bg-saved-snapshot-recovery-v1"
recovery.replacement = bg_replacement.replacement
recovery.successor = bg_successor
recovery.INSTALLATION_LABEL = "BG"
recovery.PREDECESSOR_INSTALLATION_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"
recovery.PREDECESSOR_DEFINITION_REVISION = 100
recovery.TRANSFERRED_DEFINITION_REVISION = 101
recovery.RECOVERY_REVISION = 33
recovery.ENABLED_DEFINITION_REVISION = 102
recovery.PAUSED_DEFINITION_REVISION = 103
recovery.PREDECESSOR_RECOVERY_STATE = "bf-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bg-snapshot"
recovery.DISABLE_KEY = "a0v-bg-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bg-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bg-saved-input-recovery-v33"
recovery.PAUSE_KEY = "a0v-bg-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bg_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
