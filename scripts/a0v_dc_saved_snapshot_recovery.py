#!/usr/bin/env python3
"""Transfer the frozen snapshot group from DB to active DC without source reads."""
from __future__ import annotations
import a0v_db_saved_snapshot_recovery as predecessor
import a0v_dc_replacement_recovery as dc_replacement
import a0v_dc_successor_business as dc_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "dc-saved-snapshot-recovery-v1"
recovery.replacement = dc_replacement.replacement
recovery.successor = dc_successor
recovery.INSTALLATION_LABEL = "DC"
recovery.PREDECESSOR_INSTALLATION_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"
recovery.PREDECESSOR_DEFINITION_REVISION = 226
recovery.TRANSFERRED_DEFINITION_REVISION = 227
recovery.RECOVERY_REVISION = 75
recovery.ENABLED_DEFINITION_REVISION = 228
recovery.PAUSED_DEFINITION_REVISION = 229
recovery.PREDECESSOR_RECOVERY_STATE = "db-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-dc-snapshot"
recovery.DISABLE_KEY = "a0v-dc-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-dc-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-dc-saved-input-recovery-v75"
recovery.PAUSE_KEY = "a0v-dc-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = dc_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = dc_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = dc_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:b07f0b5552f66117e4006143999b5ccea65d49efe02b2c0d0d98389bbea405ab"


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
            or current["body"]["revision"] != 226 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 74
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed DB recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 227
            or result.get("body", {}).get("installationId") != dc_successor.DC_ID
            or result.get("body", {}).get("generation") != dc_successor.DC_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled DC transferred definition required")
    return {"outcome": "DC_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_dc_attempt_guard as guard
    return guard


def _setup():
    return None, None, dc_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
