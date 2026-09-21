#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CW to active CX without source reads."""
from __future__ import annotations
import a0v_cw_saved_snapshot_recovery as predecessor
import a0v_cx_replacement_recovery as cx_replacement
import a0v_cx_successor_business as cx_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "cx-saved-snapshot-recovery-v1"
recovery.replacement = cx_replacement.replacement
recovery.successor = cx_successor
recovery.INSTALLATION_LABEL = "CX"
recovery.PREDECESSOR_INSTALLATION_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"
recovery.PREDECESSOR_DEFINITION_REVISION = 211
recovery.TRANSFERRED_DEFINITION_REVISION = 212
recovery.RECOVERY_REVISION = 70
recovery.ENABLED_DEFINITION_REVISION = 213
recovery.PAUSED_DEFINITION_REVISION = 214
recovery.PREDECESSOR_RECOVERY_STATE = "cw-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-cx-snapshot"
recovery.DISABLE_KEY = "a0v-cx-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-cx-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-cx-saved-input-recovery-v70"
recovery.PAUSE_KEY = "a0v-cx-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = cx_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = cx_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = cx_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:d03e6744c2d58040157332409945c6d67073eba4a5b5592a96459d6eeba276f5"


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
            or current["body"]["revision"] != 211 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 69
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CW recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 212
            or result.get("body", {}).get("installationId") != cx_successor.CX_ID
            or result.get("body", {}).get("generation") != cx_successor.CX_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CX transferred definition required")
    return {"outcome": "CX_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_cx_attempt_guard as guard
    return guard


def _setup():
    return None, None, cx_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
