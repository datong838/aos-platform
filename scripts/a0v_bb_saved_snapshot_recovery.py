#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BA to active BB without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bb_replacement_recovery as bb_replacement
import a0v_bb_successor_business as bb_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bb-saved-snapshot-recovery-v1"
recovery.replacement = bb_replacement.replacement
recovery.successor = bb_successor
recovery.INSTALLATION_LABEL = "BB"
recovery.PREDECESSOR_INSTALLATION_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"
recovery.PREDECESSOR_DEFINITION_REVISION = 85
recovery.TRANSFERRED_DEFINITION_REVISION = 86
recovery.RECOVERY_REVISION = 28
recovery.ENABLED_DEFINITION_REVISION = 87
recovery.PAUSED_DEFINITION_REVISION = 88
recovery.PREDECESSOR_RECOVERY_STATE = "ba-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bb-snapshot"
recovery.DISABLE_KEY = "a0v-bb-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bb-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bb-saved-input-recovery-v28"
recovery.PAUSE_KEY = "a0v-bb-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bb_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
