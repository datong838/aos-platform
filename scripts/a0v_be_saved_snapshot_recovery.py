#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BD to active BE without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_be_replacement_recovery as be_replacement
import a0v_be_successor_business as be_successor


recovery.STATE = recovery.snapshot.STATE.parent / "be-saved-snapshot-recovery-v1"
recovery.replacement = be_replacement.replacement
recovery.successor = be_successor
recovery.INSTALLATION_LABEL = "BE"
recovery.PREDECESSOR_INSTALLATION_ID = "c2d6ef97-30ec-4980-9421-54a899607853"
recovery.PREDECESSOR_DEFINITION_REVISION = 94
recovery.TRANSFERRED_DEFINITION_REVISION = 95
recovery.RECOVERY_REVISION = 31
recovery.ENABLED_DEFINITION_REVISION = 96
recovery.PAUSED_DEFINITION_REVISION = 97
recovery.PREDECESSOR_RECOVERY_STATE = "bd-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-be-snapshot"
recovery.DISABLE_KEY = "a0v-be-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-be-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-be-saved-input-recovery-v31"
recovery.PAUSE_KEY = "a0v-be-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_be_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
