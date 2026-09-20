#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BI to active BJ without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bj_replacement_recovery as bj_replacement
import a0v_bj_successor_business as bj_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bj-saved-snapshot-recovery-v1"
recovery.replacement = bj_replacement.replacement
recovery.successor = bj_successor
recovery.INSTALLATION_LABEL = "BJ"
recovery.PREDECESSOR_INSTALLATION_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"
recovery.PREDECESSOR_DEFINITION_REVISION = 109
recovery.TRANSFERRED_DEFINITION_REVISION = 110
recovery.RECOVERY_REVISION = 36
recovery.ENABLED_DEFINITION_REVISION = 111
recovery.PAUSED_DEFINITION_REVISION = 112
recovery.PREDECESSOR_RECOVERY_STATE = "bi-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bj-snapshot"
recovery.DISABLE_KEY = "a0v-bj-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bj-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bj-saved-input-recovery-v36"
recovery.PAUSE_KEY = "a0v-bj-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bj_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
