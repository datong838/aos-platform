#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CA to active CB without source reads."""
from __future__ import annotations

import a0v_ca_saved_snapshot_recovery as predecessor
import a0v_cb_replacement_recovery as cb_replacement
import a0v_cb_successor_business as cb_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight


recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "cb-saved-snapshot-recovery-v1"
recovery.replacement = cb_replacement.replacement
recovery.successor = cb_successor
recovery.INSTALLATION_LABEL = "CB"
recovery.PREDECESSOR_INSTALLATION_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"
recovery.PREDECESSOR_DEFINITION_REVISION = 148
recovery.TRANSFERRED_DEFINITION_REVISION = 149
recovery.RECOVERY_REVISION = 49
recovery.ENABLED_DEFINITION_REVISION = 150
recovery.PAUSED_DEFINITION_REVISION = 151
recovery.PREDECESSOR_RECOVERY_STATE = "ca-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-cb-snapshot"
recovery.DISABLE_KEY = "a0v-cb-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-cb-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-cb-saved-input-recovery-v49"
recovery.PAUSE_KEY = "a0v-cb-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = cb_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = cb_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = cb_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:d6549653845e2e3bad2766bc8dbbdf5b43ff9497efc72e455d4d5fa75b25e728"


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
            or recovery_ref.get("revision") != 48
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CA recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 149
            or result.get("body", {}).get("installationId") != cb_successor.CB_ID
            or result.get("body", {}).get("generation") != cb_successor.CB_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CB transferred definition required")
    return {"outcome": "CB_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_cb_attempt_guard as guard
    return guard


def _setup():
    return None, None, cb_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer


if __name__ == "__main__":
    recovery.main()
