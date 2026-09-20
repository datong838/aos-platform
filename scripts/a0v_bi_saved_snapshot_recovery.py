#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BH to active BI without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bi_replacement_recovery as bi_replacement
import a0v_bi_successor_business as bi_successor


recovery.STATE = recovery.snapshot.STATE.parent / "bi-saved-snapshot-recovery-v1"
recovery.replacement = bi_replacement.replacement
recovery.successor = bi_successor
recovery.INSTALLATION_LABEL = "BI"
recovery.PREDECESSOR_INSTALLATION_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"
recovery.PREDECESSOR_DEFINITION_REVISION = 106
recovery.TRANSFERRED_DEFINITION_REVISION = 107
recovery.RECOVERY_REVISION = 35
recovery.ENABLED_DEFINITION_REVISION = 108
recovery.PAUSED_DEFINITION_REVISION = 109
recovery.PREDECESSOR_RECOVERY_STATE = "bh-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bi-snapshot"
recovery.DISABLE_KEY = "a0v-bi-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bi-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bi-saved-input-recovery-v35"
recovery.PAUSE_KEY = "a0v-bi-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_bi_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
