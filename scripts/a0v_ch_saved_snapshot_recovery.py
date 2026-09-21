#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CG to active CH without source reads."""
from __future__ import annotations
import a0v_cg_saved_snapshot_recovery as predecessor
import a0v_ch_replacement_recovery as ch_replacement
import a0v_ch_successor_business as ch_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "ch-saved-snapshot-recovery-v1"
recovery.replacement = ch_replacement.replacement
recovery.successor = ch_successor
recovery.INSTALLATION_LABEL = "CH"
recovery.PREDECESSOR_INSTALLATION_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"
recovery.PREDECESSOR_DEFINITION_REVISION = 166
recovery.TRANSFERRED_DEFINITION_REVISION = 167
recovery.RECOVERY_REVISION = 55
recovery.ENABLED_DEFINITION_REVISION = 168
recovery.PAUSED_DEFINITION_REVISION = 169
recovery.PREDECESSOR_RECOVERY_STATE = "cg-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-ch-snapshot"
recovery.DISABLE_KEY = "a0v-ch-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-ch-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-ch-saved-input-recovery-v55"
recovery.PAUSE_KEY = "a0v-ch-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = ch_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = ch_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = ch_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:c9536786347d902ff87a9a06613df5644dfb6d9597afbf39733cc6aa0539ed58"


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
            or current["body"]["revision"] != 166 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 54
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CG recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 167
            or result.get("body", {}).get("installationId") != ch_successor.CH_ID
            or result.get("body", {}).get("generation") != ch_successor.CH_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CH transferred definition required")
    return {"outcome": "CH_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_ch_attempt_guard as guard
    return guard


def _setup():
    return None, None, ch_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
