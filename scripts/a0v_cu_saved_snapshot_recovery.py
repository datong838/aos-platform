#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CT to active CU without source reads."""
from __future__ import annotations
import a0v_ct_saved_snapshot_recovery as predecessor
import a0v_cu_replacement_recovery as cu_replacement
import a0v_cu_successor_business as cu_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "cu-saved-snapshot-recovery-v1"
recovery.replacement = cu_replacement.replacement
recovery.successor = cu_successor
recovery.INSTALLATION_LABEL = "CU"
recovery.PREDECESSOR_INSTALLATION_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"
recovery.PREDECESSOR_DEFINITION_REVISION = 202
recovery.TRANSFERRED_DEFINITION_REVISION = 203
recovery.RECOVERY_REVISION = 67
recovery.ENABLED_DEFINITION_REVISION = 204
recovery.PAUSED_DEFINITION_REVISION = 205
recovery.PREDECESSOR_RECOVERY_STATE = "ct-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-cu-snapshot"
recovery.DISABLE_KEY = "a0v-cu-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-cu-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-cu-saved-input-recovery-v67"
recovery.PAUSE_KEY = "a0v-cu-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = cu_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = cu_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = cu_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:8090c986e3c22b2548a14e793dc8376230bdb262aedd84f10083e2139605230a"


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
            or current["body"]["revision"] != 202 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 66
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CT recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 203
            or result.get("body", {}).get("installationId") != cu_successor.CU_ID
            or result.get("body", {}).get("generation") != cu_successor.CU_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CU transferred definition required")
    return {"outcome": "CU_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_cu_attempt_guard as guard
    return guard


def _setup():
    return None, None, cu_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
