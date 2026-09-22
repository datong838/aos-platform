#!/usr/bin/env python3
"""Transfer the frozen snapshot group from DF to active DG without source reads."""
from __future__ import annotations
import a0v_df_saved_snapshot_recovery as predecessor
import a0v_dg_replacement_recovery as dg_replacement
import a0v_dg_successor_business as dg_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = dg_replacement.replacement.STATE / "dg-saved-snapshot-recovery-v1"
recovery.replacement = dg_replacement.replacement
recovery.successor = dg_successor
recovery.INSTALLATION_LABEL = "DG"
recovery.PREDECESSOR_INSTALLATION_ID = "a0639f78-af04-4249-97f6-d8507de45f44"
recovery.PREDECESSOR_DEFINITION_REVISION = 238
recovery.TRANSFERRED_DEFINITION_REVISION = 239
recovery.RECOVERY_REVISION = 79
recovery.ENABLED_DEFINITION_REVISION = 240
recovery.PAUSED_DEFINITION_REVISION = 241
recovery.PREDECESSOR_RECOVERY_STATE = "df-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-dg-snapshot"
recovery.DISABLE_KEY = "a0v-dg-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-dg-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-dg-saved-input-recovery-v79"
recovery.PAUSE_KEY = "a0v-dg-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = dg_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = dg_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = dg_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:16ec5ac89f55dd59c04a042c0638b799b58cdd068fa5ae4d300736a6c1ff2a10"


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
            or current["body"]["revision"] != 238 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 78
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed DF recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 239
            or result.get("body", {}).get("installationId") != dg_successor.DG_ID
            or result.get("body", {}).get("generation") != dg_successor.DG_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled DG transferred definition required")
    return {"outcome": "DG_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_dg_attempt_guard as guard
    return guard


def _setup():
    return None, None, dg_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
