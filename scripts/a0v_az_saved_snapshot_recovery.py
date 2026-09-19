#!/usr/bin/env python3
"""Transfer the frozen snapshot group from AX to active AZ without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_az_replacement_recovery as az_replacement
import a0v_az_successor_business as az_successor


recovery.STATE = recovery.snapshot.STATE.parent / "az-saved-snapshot-recovery-v1"
recovery.replacement = az_replacement.replacement
recovery.successor = az_successor
recovery.INSTALLATION_LABEL = "AZ"
recovery.PREDECESSOR_INSTALLATION_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"
recovery.PREDECESSOR_DEFINITION_REVISION = 79
recovery.TRANSFERRED_DEFINITION_REVISION = 80
recovery.RECOVERY_REVISION = 26
recovery.ENABLED_DEFINITION_REVISION = 81
recovery.PAUSED_DEFINITION_REVISION = 82
recovery.PREDECESSOR_RECOVERY_STATE = "ax-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-az-snapshot"
recovery.DISABLE_KEY = "a0v-az-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-az-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-az-saved-input-recovery-v26"
recovery.PAUSE_KEY = "a0v-az-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}

# Re-export the immutable manifest so the AZ-only read guard does not need to
# reach through the shared implementation module.
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP


def attempt_guard_module():
    import a0v_az_attempt_guard as guard
    return guard


recovery.attempt_guard_module = attempt_guard_module


if __name__ == "__main__":
    recovery.main()
