#!/usr/bin/env python3
"""Transfer the frozen snapshot group from DA to active DB without source reads."""
from __future__ import annotations
import a0v_da_saved_snapshot_recovery as predecessor
import a0v_db_replacement_recovery as db_replacement
import a0v_db_successor_business as db_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "db-saved-snapshot-recovery-v1"
recovery.replacement = db_replacement.replacement
recovery.successor = db_successor
recovery.INSTALLATION_LABEL = "DB"
recovery.PREDECESSOR_INSTALLATION_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"
recovery.PREDECESSOR_DEFINITION_REVISION = 223
recovery.TRANSFERRED_DEFINITION_REVISION = 224
recovery.RECOVERY_REVISION = 74
recovery.ENABLED_DEFINITION_REVISION = 225
recovery.PAUSED_DEFINITION_REVISION = 226
recovery.PREDECESSOR_RECOVERY_STATE = "da-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-db-snapshot"
recovery.DISABLE_KEY = "a0v-db-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-db-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-db-saved-input-recovery-v74"
recovery.PAUSE_KEY = "a0v-db-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = db_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = db_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = db_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:13d1f720afe37c554549a5c8605448fb3df7a85f519b92fdae367f0653477cdc"


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
            or current["body"]["revision"] != 223 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 73
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed DA recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 224
            or result.get("body", {}).get("installationId") != db_successor.DB_ID
            or result.get("body", {}).get("generation") != db_successor.DB_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled DB transferred definition required")
    return {"outcome": "DB_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_db_attempt_guard as guard
    return guard


def _setup():
    return None, None, db_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
