#!/usr/bin/env python3
"""Transfer the frozen snapshot group from AZ to active BA without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_ba_replacement_recovery as ba_replacement
import a0v_ba_successor_business as ba_successor


recovery.STATE = recovery.snapshot.STATE.parent / "ba-saved-snapshot-recovery-v1"
recovery.replacement = ba_replacement.replacement
recovery.successor = ba_successor
recovery.INSTALLATION_LABEL = "BA"
recovery.PREDECESSOR_INSTALLATION_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"
recovery.PREDECESSOR_DEFINITION_REVISION = 82
recovery.TRANSFERRED_DEFINITION_REVISION = 83
recovery.RECOVERY_REVISION = 27
recovery.ENABLED_DEFINITION_REVISION = 84
recovery.PAUSED_DEFINITION_REVISION = 85
recovery.PREDECESSOR_RECOVERY_STATE = "az-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-ba-snapshot"
recovery.DISABLE_KEY = "a0v-ba-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-ba-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-ba-saved-input-recovery-v27"
recovery.PAUSE_KEY = "a0v-ba-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_ba_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
