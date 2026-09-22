#!/usr/bin/env python3
"""Transfer the frozen snapshot group from DG to active DH without source reads."""
from __future__ import annotations
import a0v_dg_saved_snapshot_recovery as predecessor
import a0v_dh_replacement_recovery as dh_replacement
import a0v_dh_successor_business as dh_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = dh_replacement.replacement.STATE / "dh-saved-snapshot-recovery-v1"
recovery.replacement = dh_replacement.replacement
recovery.successor = dh_successor
recovery.INSTALLATION_LABEL = "DH"
recovery.PREDECESSOR_INSTALLATION_ID = "d551d104-f240-4b27-b738-1ef47129b5a4"
recovery.PREDECESSOR_DEFINITION_REVISION = 241
recovery.TRANSFERRED_DEFINITION_REVISION = 242
recovery.RECOVERY_REVISION = 80
recovery.ENABLED_DEFINITION_REVISION = 243
recovery.PAUSED_DEFINITION_REVISION = 244
recovery.PREDECESSOR_RECOVERY_STATE = "dg-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-dh-snapshot"
recovery.DISABLE_KEY = "a0v-dh-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-dh-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-dh-saved-input-recovery-v80"
recovery.PAUSE_KEY = "a0v-dh-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = dh_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = dh_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = dh_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:1c1e3cd66d597f5157eb6be4f4d6a00a9b50f5d077c5329f026247398d5f6ca4"


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
            or current["body"]["revision"] != 241 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 79
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed DG recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 242
            or result.get("body", {}).get("installationId") != dh_successor.DH_ID
            or result.get("body", {}).get("generation") != dh_successor.DH_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled DH transferred definition required")
    return {"outcome": "DH_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_dh_attempt_guard as guard
    return guard


def _setup():
    return None, None, dh_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
