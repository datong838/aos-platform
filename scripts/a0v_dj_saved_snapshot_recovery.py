#!/usr/bin/env python3
"""Transfer the frozen snapshot group from DI to active DJ without source reads."""
from __future__ import annotations
import a0v_di_saved_snapshot_recovery as predecessor
import a0v_dj_replacement_recovery as dj_replacement
import a0v_dj_successor_business as dj_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = dj_replacement.replacement.STATE / "dj-saved-snapshot-recovery-v1"
recovery.replacement = dj_replacement.replacement
recovery.successor = dj_successor
recovery.INSTALLATION_LABEL = "DJ"
recovery.PREDECESSOR_INSTALLATION_ID = "c8298a5d-9d94-4c37-81c9-508e2f0faf60"
recovery.PREDECESSOR_DEFINITION_REVISION = 247
recovery.TRANSFERRED_DEFINITION_REVISION = 248
recovery.RECOVERY_REVISION = 82
recovery.ENABLED_DEFINITION_REVISION = 249
recovery.PAUSED_DEFINITION_REVISION = 250
recovery.PREDECESSOR_RECOVERY_STATE = "di-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-dj-snapshot"
recovery.DISABLE_KEY = "a0v-dj-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-dj-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-dj-saved-input-recovery-v82"
recovery.PAUSE_KEY = "a0v-dj-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = dj_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = dj_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = dj_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:3831357759bd96db97ff3e24417a5b1841b9203ae608d8b20a89feccef0b6d0c"


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
            or current["body"]["revision"] != 247 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 81
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed DI recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 248
            or result.get("body", {}).get("installationId") != dj_successor.DJ_ID
            or result.get("body", {}).get("generation") != dj_successor.DJ_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled DJ transferred definition required")
    return {"outcome": "DJ_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_dj_attempt_guard as guard
    return guard


def _setup():
    return None, None, dj_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
