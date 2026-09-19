#!/usr/bin/env python3
"""Transfer the frozen snapshot group from retired AV to active AW without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_aw_replacement_recovery as aw_replacement
import a0v_aw_successor_business as aw_successor


recovery.STATE = recovery.snapshot.STATE.parent / "aw-saved-snapshot-recovery-v1"
recovery.replacement = aw_replacement.replacement
recovery.successor = aw_successor
recovery.INSTALLATION_LABEL = "AW"
recovery.PREDECESSOR_INSTALLATION_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"
recovery.PREDECESSOR_DEFINITION_REVISION = 76
recovery.TRANSFERRED_DEFINITION_REVISION = 77
recovery.RECOVERY_REVISION = 25
recovery.ENABLED_DEFINITION_REVISION = 78
recovery.PAUSED_DEFINITION_REVISION = 79
recovery.PREDECESSOR_RECOVERY_STATE = "av-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-aw-snapshot"
recovery.DISABLE_KEY = "a0v-aw-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-aw-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-aw-saved-input-recovery-v25"
recovery.PAUSE_KEY = "a0v-aw-saved-snapshot-pause-terminal-v1"


if __name__ == "__main__":
    recovery.main()
