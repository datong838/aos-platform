#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BB to active BC without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bc_replacement_recovery as bc_replacement
import a0v_bc_successor_business as bc_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bc-saved-snapshot-recovery-v1"
recovery.replacement = bc_replacement.replacement
recovery.successor = bc_successor
recovery.INSTALLATION_LABEL = "BC"
recovery.PREDECESSOR_INSTALLATION_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"
recovery.PREDECESSOR_DEFINITION_REVISION = 88
recovery.TRANSFERRED_DEFINITION_REVISION = 89
recovery.RECOVERY_REVISION = 29
recovery.ENABLED_DEFINITION_REVISION = 90
recovery.PAUSED_DEFINITION_REVISION = 91
recovery.PREDECESSOR_RECOVERY_STATE = "bb-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bc-snapshot"
recovery.DISABLE_KEY = "a0v-bc-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bc-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bc-saved-input-recovery-v29"
recovery.PAUSE_KEY = "a0v-bc-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bc_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
