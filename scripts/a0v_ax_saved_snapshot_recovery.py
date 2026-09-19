#!/usr/bin/env python3
"""Transfer the frozen snapshot group from current AV authority to active AX without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_ax_attempt_guard as ax_guard
import a0v_ax_replacement_recovery as ax_replacement
import a0v_ax_successor_business as ax_successor


recovery.STATE = recovery.snapshot.STATE.parent / "ax-saved-snapshot-recovery-v1"
recovery.replacement = ax_replacement.replacement
recovery.successor = ax_successor
recovery.INSTALLATION_LABEL = "AX"
recovery.PREDECESSOR_INSTALLATION_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"
recovery.PREDECESSOR_DEFINITION_REVISION = 76
recovery.TRANSFERRED_DEFINITION_REVISION = 77
recovery.RECOVERY_REVISION = 25
recovery.ENABLED_DEFINITION_REVISION = 78
recovery.PAUSED_DEFINITION_REVISION = 79
recovery.PREDECESSOR_RECOVERY_STATE = "av-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-ax-snapshot"
recovery.DISABLE_KEY = "a0v-ax-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-ax-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-ax-saved-input-recovery-v25"
recovery.PAUSE_KEY = "a0v-ax-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.attempt_guard_module = lambda: ax_guard


if __name__ == "__main__":
    recovery.main()
