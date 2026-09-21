#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CL to active CM without source reads."""
from __future__ import annotations
import a0v_cl_saved_snapshot_recovery as predecessor
import a0v_cm_replacement_recovery as cm_replacement
import a0v_cm_successor_business as cm_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "cm-saved-snapshot-recovery-v1"
recovery.replacement = cm_replacement.replacement
recovery.successor = cm_successor
recovery.INSTALLATION_LABEL = "CM"
recovery.PREDECESSOR_INSTALLATION_ID = "64e49f66-b0ef-4676-91c1-eb05f6d1d0b1"
recovery.PREDECESSOR_DEFINITION_REVISION = 181
recovery.TRANSFERRED_DEFINITION_REVISION = 182
recovery.RECOVERY_REVISION = 60
recovery.ENABLED_DEFINITION_REVISION = 183
recovery.PAUSED_DEFINITION_REVISION = 184
recovery.PREDECESSOR_RECOVERY_STATE = "cl-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-cm-snapshot"
recovery.DISABLE_KEY = "a0v-cm-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-cm-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-cm-saved-input-recovery-v60"
recovery.PAUSE_KEY = "a0v-cm-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = cm_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = cm_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = cm_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:398205f8a032adc5af6fad259ba7780f600340382a7b542530725c0d78fd426f"


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
            or current["body"]["revision"] != 181 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 59
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CL recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 182
            or result.get("body", {}).get("installationId") != cm_successor.CM_ID
            or result.get("body", {}).get("generation") != cm_successor.CM_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CM transferred definition required")
    return {"outcome": "CM_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_cm_attempt_guard as guard
    return guard


def _setup():
    return None, None, cm_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
