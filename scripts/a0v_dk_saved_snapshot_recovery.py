#!/usr/bin/env python3
"""Transfer the frozen snapshot group from DJ to active DK without source reads."""
from __future__ import annotations
import a0v_dj_saved_snapshot_recovery as predecessor
import a0v_dk_replacement_recovery as dk_replacement
import a0v_dk_successor_business as dk_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = dk_replacement.replacement.STATE / "dk-saved-snapshot-recovery-v1"
recovery.replacement = dk_replacement.replacement
recovery.successor = dk_successor
recovery.INSTALLATION_LABEL = "DK"
recovery.PREDECESSOR_INSTALLATION_ID = "aca93a08-341f-4bd6-9e94-ed7fde3aed66"
recovery.PREDECESSOR_DEFINITION_REVISION = 250
recovery.TRANSFERRED_DEFINITION_REVISION = 251
recovery.RECOVERY_REVISION = 83
recovery.ENABLED_DEFINITION_REVISION = 252
recovery.PAUSED_DEFINITION_REVISION = 253
recovery.PREDECESSOR_RECOVERY_STATE = "dj-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-dk-snapshot"
recovery.DISABLE_KEY = "a0v-dk-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-dk-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-dk-saved-input-recovery-v83"
recovery.PAUSE_KEY = "a0v-dk-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = dk_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = dk_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = dk_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:52d22d57c12bbbfe46328b35dcf130858e9b86548703795b0a7b593a1336e57f"


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
            or current["body"]["revision"] != 250 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 82
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed DJ recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 251
            or result.get("body", {}).get("installationId") != dk_successor.DK_ID
            or result.get("body", {}).get("generation") != dk_successor.DK_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled DK transferred definition required")
    return {"outcome": "DK_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_dk_attempt_guard as guard
    return guard


def _setup():
    return None, None, dk_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
