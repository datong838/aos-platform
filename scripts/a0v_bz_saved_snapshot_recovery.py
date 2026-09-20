#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BY to active BZ without source reads."""
from __future__ import annotations

import a0v_by_saved_snapshot_recovery as predecessor
import a0v_bz_replacement_recovery as bz_replacement
import a0v_bz_successor_business as bz_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight


recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "bz-saved-snapshot-recovery-v1"
recovery.replacement = bz_replacement.replacement
recovery.successor = bz_successor
recovery.INSTALLATION_LABEL = "BZ"
recovery.PREDECESSOR_INSTALLATION_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"
recovery.PREDECESSOR_DEFINITION_REVISION = 142
recovery.TRANSFERRED_DEFINITION_REVISION = 143
recovery.RECOVERY_REVISION = 47
recovery.ENABLED_DEFINITION_REVISION = 144
recovery.PAUSED_DEFINITION_REVISION = 145
recovery.PREDECESSOR_RECOVERY_STATE = "by-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bz-snapshot"
recovery.DISABLE_KEY = "a0v-bz-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bz-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bz-saved-input-recovery-v47"
recovery.PAUSE_KEY = "a0v-bz-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = bz_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = bz_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = bz_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:a0e1a232f699d30d97c95cf7143665c6976033b6cf011b55ff783e20bc586142"


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
            or recovery_ref.get("revision") != 46
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed BY recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 143
            or result.get("body", {}).get("installationId") != bz_successor.BZ_ID
            or result.get("body", {}).get("generation") != bz_successor.BZ_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled BZ transferred definition required")
    return {"outcome": "BZ_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_bz_attempt_guard as guard
    return guard


def _setup():
    return None, None, bz_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer


if __name__ == "__main__":
    recovery.main()
