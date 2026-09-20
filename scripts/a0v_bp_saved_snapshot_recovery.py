#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BO to active BP without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bp_replacement_recovery as bp_replacement
import a0v_bp_successor_business as bp_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight


recovery.STATE = recovery.snapshot.STATE.parent / "bp-saved-snapshot-recovery-v1"
recovery.replacement = bp_replacement.replacement
recovery.successor = bp_successor
recovery.INSTALLATION_LABEL = "BP"
recovery.PREDECESSOR_INSTALLATION_ID = "307399a0-21bb-4d55-95b2-8b0fee238913"
recovery.PREDECESSOR_DEFINITION_REVISION = 121
recovery.TRANSFERRED_DEFINITION_REVISION = 122
recovery.RECOVERY_REVISION = 40
recovery.ENABLED_DEFINITION_REVISION = 123
recovery.PAUSED_DEFINITION_REVISION = 124
recovery.PREDECESSOR_RECOVERY_STATE = "bo-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bp-snapshot"
recovery.DISABLE_KEY = "a0v-bp-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bp-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bp-saved-input-recovery-v40"
recovery.PAUSE_KEY = "a0v-bp-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {
    "FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"
}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = bp_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = bp_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = bp_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:39ca604ec957db0f8a7b20fedecd11f25e3ed8d60e3cc0feea56d6568d8cc2ec"


def transfer(plane):
    """Transfer from the exact database-backed BO recovery."""
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope

    service, members = recovery.service_and_options(plane)
    scope = TenantScope(**recovery.snapshot.baseline.SCOPE)
    with consumer_connection(runtime_worker_connection, recovery.snapshot.baseline.SCOPE) as conn:
        current = service._owner.read(
            conn, scope=scope, definition_id=recovery.snapshot.DEFINITION_ID)
    context = service.read_recovery_context(group_id=GROUP, actor=recovery.snapshot.ACTOR)
    recovery_ref = context.get("expectedRecoveryRef")
    if (
        current is None
        or current["body"]["state"] != "disabled"
        or current["body"]["installationId"] != recovery.PREDECESSOR_INSTALLATION_ID
        or current["body"]["revision"] != recovery.PREDECESSOR_DEFINITION_REVISION
        or context.get("expectedDefinitionRef") != current["ref"]
        or recovery_ref is None
        or recovery_ref.get("revision") != 39
        or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH
    ):
        raise RuntimeError("exact database-backed BO recovery boundary required")
    result = service.transfer_saved_recovery(
        definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP,
        actor=recovery.snapshot.ACTOR,
        members=members,
        expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref,
        idempotency_key=recovery.TRANSFER_KEY,
    )
    if (
        result.get("ref", {}).get("revision") != recovery.TRANSFERRED_DEFINITION_REVISION
        or result.get("body", {}).get("revision") != recovery.TRANSFERRED_DEFINITION_REVISION
        or result.get("body", {}).get("priorRef") != current["ref"]
        or result.get("body", {}).get("installationId") != bp_successor.BP_ID
        or result.get("body", {}).get("generation") != bp_successor.BP_GENERATION
        or result.get("body", {}).get("state") != "disabled"
    ):
        raise RuntimeError("exact disabled BP transferred definition required")
    return {
        "outcome": "BP_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED",
        "definition": result,
        "groupId": GROUP,
        "inputManifestHash": MANIFEST,
        "predecessorRecoveryRef": recovery_ref,
        "sourceReads": 0,
    }


def attempt_guard_module():
    import a0v_bp_attempt_guard as guard
    return guard


def _setup():
    return None, None, bp_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer


if __name__ == "__main__":
    recovery.main()
