#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BL to active BO without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bo_replacement_recovery as bo_replacement
import a0v_bo_successor_business as bo_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight


recovery.STATE = recovery.snapshot.STATE.parent / "bo-saved-snapshot-recovery-v1"
recovery.replacement = bo_replacement.replacement
recovery.successor = bo_successor
recovery.INSTALLATION_LABEL = "BO"
recovery.PREDECESSOR_INSTALLATION_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"
recovery.PREDECESSOR_DEFINITION_REVISION = 118
recovery.TRANSFERRED_DEFINITION_REVISION = 119
recovery.RECOVERY_REVISION = 39
recovery.ENABLED_DEFINITION_REVISION = 120
recovery.PAUSED_DEFINITION_REVISION = 121
recovery.PREDECESSOR_RECOVERY_STATE = "bl-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bo-snapshot"
recovery.DISABLE_KEY = "a0v-bo-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bo-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bo-saved-input-recovery-v39"
recovery.PAUSE_KEY = "a0v-bo-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {
    "FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"
}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = bo_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = bo_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = bo_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"

MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:9f81de0cdf898e3ea316c9d58ba20c95103741c1401af771b2379fe9ced22be7"


def transfer(plane):
    """Transfer from the exact database-backed BL recovery after local evidence loss."""
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
        or recovery_ref.get("revision") != 38
        or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH
    ):
        raise RuntimeError("exact database-backed BL recovery boundary required")
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
        or result.get("body", {}).get("installationId") != bo_successor.BO_ID
        or result.get("body", {}).get("generation") != bo_successor.BO_GENERATION
        or result.get("body", {}).get("state") != "disabled"
    ):
        raise RuntimeError("exact disabled BO transferred definition required")
    return {
        "outcome": "BO_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED",
        "definition": result,
        "groupId": GROUP,
        "inputManifestHash": MANIFEST,
        "predecessorRecoveryRef": recovery_ref,
        "sourceReads": 0,
    }


def attempt_guard_module():
    import a0v_bo_attempt_guard as guard
    return guard


def _setup():
    return None, None, bo_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer


if __name__ == "__main__":
    recovery.main()
