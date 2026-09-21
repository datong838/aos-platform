#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CF to active CG without source reads."""
from __future__ import annotations
import a0v_cf_saved_snapshot_recovery as predecessor
import a0v_cg_replacement_recovery as cg_replacement
import a0v_cg_successor_business as cg_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "cg-saved-snapshot-recovery-v1"
recovery.replacement = cg_replacement.replacement
recovery.successor = cg_successor
recovery.INSTALLATION_LABEL = "CG"
recovery.PREDECESSOR_INSTALLATION_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"
recovery.PREDECESSOR_DEFINITION_REVISION = 163
recovery.TRANSFERRED_DEFINITION_REVISION = 164
recovery.RECOVERY_REVISION = 54
recovery.ENABLED_DEFINITION_REVISION = 165
recovery.PAUSED_DEFINITION_REVISION = 166
recovery.PREDECESSOR_RECOVERY_STATE = "cf-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-cg-snapshot"
recovery.DISABLE_KEY = "a0v-cg-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-cg-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-cg-saved-input-recovery-v54"
recovery.PAUSE_KEY = "a0v-cg-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = cg_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = cg_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = cg_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:de7600063dce230701986d346b616e9b4a9bbe185d01998541cb67128b300a42"


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
            or current["body"]["revision"] != 163 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 53
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CF recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 164
            or result.get("body", {}).get("installationId") != cg_successor.CG_ID
            or result.get("body", {}).get("generation") != cg_successor.CG_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CG transferred definition required")
    return {"outcome": "CG_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_cg_attempt_guard as guard
    return guard


def _setup():
    return None, None, cg_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
