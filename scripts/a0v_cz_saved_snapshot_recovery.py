#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CY to active CZ without source reads."""
from __future__ import annotations
import a0v_cy_saved_snapshot_recovery as predecessor
import a0v_cz_replacement_recovery as cz_replacement
import a0v_cz_successor_business as cz_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "cz-saved-snapshot-recovery-v1"
recovery.replacement = cz_replacement.replacement
recovery.successor = cz_successor
recovery.INSTALLATION_LABEL = "CZ"
recovery.PREDECESSOR_INSTALLATION_ID = "917cd341-96a5-4428-9508-03c716c587ad"
recovery.PREDECESSOR_DEFINITION_REVISION = 217
recovery.TRANSFERRED_DEFINITION_REVISION = 218
recovery.RECOVERY_REVISION = 72
recovery.ENABLED_DEFINITION_REVISION = 219
recovery.PAUSED_DEFINITION_REVISION = 220
recovery.PREDECESSOR_RECOVERY_STATE = "cy-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-cz-snapshot"
recovery.DISABLE_KEY = "a0v-cz-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-cz-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-cz-saved-input-recovery-v72"
recovery.PAUSE_KEY = "a0v-cz-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = cz_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = cz_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = cz_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:3f085ba307099ce825c33f8b75c8a5a7f62da436ae0b134c3825e3e050ea8131"


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
            or current["body"]["revision"] != 217 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 71
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CY recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 218
            or result.get("body", {}).get("installationId") != cz_successor.CZ_ID
            or result.get("body", {}).get("generation") != cz_successor.CZ_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CZ transferred definition required")
    return {"outcome": "CZ_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_cz_attempt_guard as guard
    return guard


def _setup():
    return None, None, cz_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
