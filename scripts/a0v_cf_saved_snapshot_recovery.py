#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CE to active CF without source reads."""
from __future__ import annotations
import a0v_ce_saved_snapshot_recovery as predecessor
import a0v_cf_replacement_recovery as cf_replacement
import a0v_cf_successor_business as cf_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "cf-saved-snapshot-recovery-v1"
recovery.replacement = cf_replacement.replacement
recovery.successor = cf_successor
recovery.INSTALLATION_LABEL = "CF"
recovery.PREDECESSOR_INSTALLATION_ID = "29d1b06d-3baa-4476-9cf8-5ea345d134c7"
recovery.PREDECESSOR_DEFINITION_REVISION = 160
recovery.TRANSFERRED_DEFINITION_REVISION = 161
recovery.RECOVERY_REVISION = 53
recovery.ENABLED_DEFINITION_REVISION = 162
recovery.PAUSED_DEFINITION_REVISION = 163
recovery.PREDECESSOR_RECOVERY_STATE = "ce-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-cf-snapshot"
recovery.DISABLE_KEY = "a0v-cf-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-cf-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-cf-saved-input-recovery-v53"
recovery.PAUSE_KEY = "a0v-cf-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = cf_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = cf_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = cf_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:77be40f32ad75219d8b763b1c1b07c06867989a5783a92dd516bd44361d44ffd"

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
            or current["body"]["revision"] != 160 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 52
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CE recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 161
            or result.get("body", {}).get("installationId") != cf_successor.CF_ID
            or result.get("body", {}).get("generation") != cf_successor.CF_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CF transferred definition required")
    return {"outcome": "CF_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}

def attempt_guard_module():
    import a0v_cf_attempt_guard as guard
    return guard

def _setup():
    return None, None, cf_successor.setup()

recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
