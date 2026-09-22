#!/usr/bin/env python3
"""Transfer the frozen snapshot group from DH to active DI without source reads."""
from __future__ import annotations
import a0v_dh_saved_snapshot_recovery as predecessor
import a0v_di_replacement_recovery as di_replacement
import a0v_di_successor_business as di_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = di_replacement.replacement.STATE / "di-saved-snapshot-recovery-v1"
recovery.replacement = di_replacement.replacement
recovery.successor = di_successor
recovery.INSTALLATION_LABEL = "DI"
recovery.PREDECESSOR_INSTALLATION_ID = "10d583ad-96ee-4b1a-bb18-92e428abe16e"
recovery.PREDECESSOR_DEFINITION_REVISION = 244
recovery.TRANSFERRED_DEFINITION_REVISION = 245
recovery.RECOVERY_REVISION = 81
recovery.ENABLED_DEFINITION_REVISION = 246
recovery.PAUSED_DEFINITION_REVISION = 247
recovery.PREDECESSOR_RECOVERY_STATE = "dh-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-di-snapshot"
recovery.DISABLE_KEY = "a0v-di-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-di-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-di-saved-input-recovery-v81"
recovery.PAUSE_KEY = "a0v-di-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = di_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = di_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = di_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:fb08b9f42322876be1e8d0f859852d5c6b5ff21d2cf720d003388534ffb69675"


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
            or current["body"]["revision"] != 244 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 80
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed DH recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 245
            or result.get("body", {}).get("installationId") != di_successor.DI_ID
            or result.get("body", {}).get("generation") != di_successor.DI_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled DI transferred definition required")
    return {"outcome": "DI_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_di_attempt_guard as guard
    return guard


def _setup():
    return None, None, di_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
