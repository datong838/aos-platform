#!/usr/bin/env python3
"""Transfer the frozen snapshot group from BU to active BV without source reads."""
from __future__ import annotations

import a0v_av_saved_snapshot_recovery as recovery
import a0v_bv_replacement_recovery as bv_replacement
import a0v_bv_successor_business as bv_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight


recovery.STATE = recovery.snapshot.STATE.parent / "bv-saved-snapshot-recovery-v1"
recovery.replacement = bv_replacement.replacement
recovery.successor = bv_successor
recovery.INSTALLATION_LABEL = "BV"
recovery.PREDECESSOR_INSTALLATION_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"
recovery.PREDECESSOR_DEFINITION_REVISION = 130
recovery.TRANSFERRED_DEFINITION_REVISION = 131
recovery.RECOVERY_REVISION = 43
recovery.ENABLED_DEFINITION_REVISION = 132
recovery.PAUSED_DEFINITION_REVISION = 133
recovery.PREDECESSOR_RECOVERY_STATE = "bu-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-bv-snapshot"
recovery.DISABLE_KEY = "a0v-bv-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-bv-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-bv-saved-input-recovery-v43"
recovery.PAUSE_KEY = "a0v-bv-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = bv_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = bv_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = bv_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:2f137e718e768aa98116af8dfa8c28a5eb66d2f3270fe8ac4c1f87b16d7cd963"


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
            or recovery_ref.get("revision") != 42
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed BU recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 131
            or result.get("body", {}).get("installationId") != bv_successor.BV_ID
            or result.get("body", {}).get("generation") != bv_successor.BV_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled BV transferred definition required")
    return {"outcome": "BV_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_bv_attempt_guard as guard
    return guard


def _setup():
    return None, None, bv_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer


if __name__ == "__main__":
    recovery.main()
