#!/usr/bin/env python3
"""Transfer the frozen snapshot group from CH to active CI without source reads."""
from __future__ import annotations
import a0v_ch_saved_snapshot_recovery as predecessor
import a0v_ci_replacement_recovery as ci_replacement
import a0v_ci_successor_business as ci_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = recovery.snapshot.STATE.parent / "ci-saved-snapshot-recovery-v1"
recovery.replacement = ci_replacement.replacement
recovery.successor = ci_successor
recovery.INSTALLATION_LABEL = "CI"
recovery.PREDECESSOR_INSTALLATION_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"
recovery.PREDECESSOR_DEFINITION_REVISION = 169
recovery.TRANSFERRED_DEFINITION_REVISION = 170
recovery.RECOVERY_REVISION = 56
recovery.ENABLED_DEFINITION_REVISION = 171
recovery.PAUSED_DEFINITION_REVISION = 172
recovery.PREDECESSOR_RECOVERY_STATE = "ch-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-ci-snapshot"
recovery.DISABLE_KEY = "a0v-ci-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-ci-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-ci-saved-input-recovery-v56"
recovery.PAUSE_KEY = "a0v-ci-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = ci_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = ci_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = ci_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:9b479ea57323740d9fc9afd4a74474a32e405dbbe0b68cc675edbc2bcefc7ebb"


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
            or current["body"]["revision"] != 169 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 55
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed CH recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 170
            or result.get("body", {}).get("installationId") != ci_successor.CI_ID
            or result.get("body", {}).get("generation") != ci_successor.CI_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled CI transferred definition required")
    return {"outcome": "CI_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_ci_attempt_guard as guard
    return guard


def _setup():
    return None, None, ci_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
if __name__ == "__main__":
    recovery.main()
