#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BC to active BD without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bd_replacement_recovery as bd_replacement
import a0v_bd_successor_business as bd_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bd-saved-snapshot-recovery-v1"
recovery.replacement = bd_replacement.replacement
recovery.successor = bd_successor
recovery.INSTALLATION_LABEL = "BD"
recovery.PREDECESSOR_INSTALLATION_ID = "3b895c30-34ca-4710-b978-02645d49c83a"
recovery.PREDECESSOR_DEFINITION_REVISION = 91
recovery.TRANSFERRED_DEFINITION_REVISION = 92
recovery.RECOVERY_REVISION = 30
recovery.ENABLED_DEFINITION_REVISION = 93
recovery.PAUSED_DEFINITION_REVISION = 94
recovery.PREDECESSOR_RECOVERY_STATE = "bc-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bd-snapshot"
recovery.DISABLE_KEY = "a0v-bd-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bd-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bd-saved-input-recovery-v30"
recovery.PAUSE_KEY = "a0v-bd-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bd_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
