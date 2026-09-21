#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CS to active CT without source reads."""
from __future__ import annotations
import a0v_cs_saved_snapshot_recovery as predecessor
import a0v_ct_replacement_recovery as ct_replacement
import a0v_ct_successor_business as ct_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "ct-saved-snapshot-recovery-v1"
recovery.replacement = ct_replacement.replacement
recovery.successor = ct_successor
recovery.INSTALLATION_LABEL = "CT"
recovery.PREDECESSOR_INSTALLATION_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"
recovery.PREDECESSOR_DEFINITION_REVISION = 199
recovery.TRANSFERRED_DEFINITION_REVISION = 200
recovery.RECOVERY_REVISION = 66
recovery.ENABLED_DEFINITION_REVISION = 201
recovery.PAUSED_DEFINITION_REVISION = 202
recovery.PREDECESSOR_RECOVERY_STATE = "cs-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-ct-snapshot"
recovery.DISABLE_KEY = "a0v-ct-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-ct-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-ct-saved-input-recovery-v66"
recovery.PAUSE_KEY = "a0v-ct-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = ct_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = ct_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = ct_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:d65a82d1bc3ffc049c3d0fe287707e894acd45456814575afdfa42b0290bf87c"


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
            or current["body"]["revision"] != 199 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 65
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CS recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 200
            or result.get("body", {}).get("installationId") != ct_successor.CT_ID
            or result.get("body", {}).get("generation") != ct_successor.CT_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CT transferred definition required")
    return {"outcome": "CT_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_ct_attempt_guard as guard
    return guard


def _setup():
    return None, None, ct_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
