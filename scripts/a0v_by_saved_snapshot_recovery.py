#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BX to active BY without source reads."""
from __future__ import annotations

import a0v_bx_saved_snapshot_recovery as predecessor
import a0v_by_replacement_recovery as by_replacement
import a0v_by_successor_business as by_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight


recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "by-saved-snapshot-recovery-v1"
recovery.replacement = by_replacement.replacement
recovery.successor = by_successor
recovery.INSTALLATION_LABEL = "BY"
recovery.PREDECESSOR_INSTALLATION_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"
recovery.PREDECESSOR_DEFINITION_REVISION = 139
recovery.TRANSFERRED_DEFINITION_REVISION = 140
recovery.RECOVERY_REVISION = 46
recovery.ENABLED_DEFINITION_REVISION = 141
recovery.PAUSED_DEFINITION_REVISION = 142
recovery.PREDECESSOR_RECOVERY_STATE = "bx-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-by-snapshot"
recovery.DISABLE_KEY = "a0v-by-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-by-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-by-saved-input-recovery-v46"
recovery.PAUSE_KEY = "a0v-by-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = by_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = by_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = by_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:f00d142e1b579f6452bd7aa57ffdde273454ce2a4ed6a8cf6fe564f1ff0463da"


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
            or recovery_ref.get("revision") != 45
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed BX recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 140
            or result.get("body", {}).get("installationId") != by_successor.BY_ID
            or result.get("body", {}).get("generation") != by_successor.BY_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled BY transferred definition required")
    return {"outcome": "BY_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_by_attempt_guard as guard
    return guard


def _setup():
    return None, None, by_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer


if __name__ == "__main__":
    recovery.main()
