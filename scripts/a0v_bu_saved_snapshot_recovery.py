#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BR to active BU without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bu_replacement_recovery as bu_replacement
import a0v_bu_successor_business as bu_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight


recovery.STATE = recovery.snapshot.STATE.parent / "bu-saved-snapshot-recovery-v1"
recovery.replacement = bu_replacement.replacement
recovery.successor = bu_successor
recovery.INSTALLATION_LABEL = "BU"
recovery.PREDECESSOR_INSTALLATION_ID = "fddfa0b0-158c-4271-b1ea-dc4e1e36e293"
recovery.PREDECESSOR_DEFINITION_REVISION = 127
recovery.TRANSFERRED_DEFINITION_REVISION = 128
recovery.RECOVERY_REVISION = 42
recovery.ENABLED_DEFINITION_REVISION = 129
recovery.PAUSED_DEFINITION_REVISION = 130
recovery.PREDECESSOR_RECOVERY_STATE = "br-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bu-snapshot"
recovery.DISABLE_KEY = "a0v-bu-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bu-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bu-saved-input-recovery-v42"
recovery.PAUSE_KEY = "a0v-bu-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = bu_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = bu_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = bu_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:400cf5d221f28501d763b194fb412a18a2c23c872057fe6e5f4c896a7721935d"


def transfer(plane):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    service, members = recovery.service_and_options(plane)
    scope = TenantScope(**recovery.snapshot.baseline.SCOPE)
    with consumer_connection(runtime_worker_connection, recovery.snapshot.baseline.SCOPE) as conn:
        current = service._owner.read(conn, scope=scope, definition_id=recovery.snapshot.DEFINITION_ID)
    context = service.read_recovery_context(group_id=GROUP, actor=recovery.snapshot.ACTOR)
    recovery_ref = context.get("expectedRecoveryRef")
    if (current is None or current["body"]["state"] != "disabled"
            or current["body"]["installationId"] != recovery.PREDECESSOR_INSTALLATION_ID
            or current["body"]["revision"] != recovery.PREDECESSOR_DEFINITION_REVISION
            or context.get("expectedDefinitionRef") != current["ref"] or recovery_ref is None
            or recovery_ref.get("revision") != 41
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed BR recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 128
            or result.get("body", {}).get("installationId") != bu_successor.BU_ID
            or result.get("body", {}).get("generation") != bu_successor.BU_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled BU transferred definition required")
    return {"outcome": "BU_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_bu_attempt_guard as guard
    return guard


def _setup():
    return None, None, bu_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer


if __name__ == "__main__":
    recovery.main()
