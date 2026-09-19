#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BE to active BF without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bf_replacement_recovery as bf_replacement
import a0v_bf_successor_business as bf_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bf-saved-snapshot-recovery-v1"
recovery.replacement = bf_replacement.replacement
recovery.successor = bf_successor
recovery.INSTALLATION_LABEL = "BF"
recovery.PREDECESSOR_INSTALLATION_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"
recovery.PREDECESSOR_DEFINITION_REVISION = 97
recovery.TRANSFERRED_DEFINITION_REVISION = 98
recovery.RECOVERY_REVISION = 32
recovery.ENABLED_DEFINITION_REVISION = 99
recovery.PAUSED_DEFINITION_REVISION = 100
recovery.PREDECESSOR_RECOVERY_STATE = "be-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bf-snapshot"
recovery.DISABLE_KEY = "a0v-bf-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bf-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bf-saved-input-recovery-v32"
recovery.PAUSE_KEY = "a0v-bf-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bf_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
