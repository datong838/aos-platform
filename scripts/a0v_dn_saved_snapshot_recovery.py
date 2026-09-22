#!/usr/bin/env python3
"""Transfer the frozen snapshot group from DM to active DN without source reads."""
from __future__ import annotations
import a0v_dm_saved_snapshot_recovery as predecessor
import a0v_dn_replacement_recovery as dn_replacement
import a0v_dn_successor_business as dn_successor
import a0v_ecommerce_runtime_host as runtime_host
import a0v_event_complete_product_api as product_api
import a0v_p02_current_preflight as current_preflight

recovery = predecessor.recovery
recovery.STATE = dn_replacement.replacement.STATE / "dn-saved-snapshot-recovery-v1"
recovery.replacement = dn_replacement.replacement
recovery.successor = dn_successor
recovery.INSTALLATION_LABEL = "DN"
recovery.PREDECESSOR_INSTALLATION_ID = "5103c27a-753e-4cad-85cb-9fa35dc0574d"
recovery.PREDECESSOR_DEFINITION_REVISION = 259
recovery.TRANSFERRED_DEFINITION_REVISION = 260
recovery.RECOVERY_REVISION = 86
recovery.ENABLED_DEFINITION_REVISION = 261
recovery.PAUSED_DEFINITION_REVISION = 262
recovery.PREDECESSOR_RECOVERY_STATE = "dm-saved-snapshot-recovery-v1"
recovery.CONTROL_PREFIX = "a0v-dn-snapshot"
recovery.DISABLE_KEY = "a0v-dn-saved-snapshot-disable-complete-v1"
recovery.TRANSFER_KEY = "a0v-dn-saved-definition-transfer-v1"
recovery.RENEW_KEY = "a0v-dn-saved-input-recovery-v86"
recovery.PAUSE_KEY = "a0v-dn-saved-snapshot-pause-terminal-v1"
recovery.TERMINAL_FREEZE_OUTCOMES = {"FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1
runtime_host.DEFAULT_CREDENTIALS = dn_replacement.canonical.CREDENTIALS
product_api.BUNDLE_ROOT = dn_replacement.replacement.BUNDLE_ROOT
current_preflight.TRUST_ROOTS = dn_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
MANIFEST = recovery.MANIFEST
GROUP = recovery.GROUP
PREDECESSOR_RECOVERY_HASH = "sha256:993275753ba8c461f9bcadbf5ce6f7d846e4aab542d500bb46b1046ed4296705"
# DN stock lifecycle etag remains 5 (unlike DM post-reset etag7).
INSTALLATION_ETAG = 5


def prepare(plane):
    """Same as AV prepare, but pin DN stock etag5 after direct successor create."""
    installation, generation = recovery.profile()
    import a0v_snapshot_current_controls as preview
    import a0v_u_twelve_source_snapshot as snapshot

    original = preview.preflight

    def preflight_etag5():
        from psycopg import Rollback
        from a0v_ecommerce_runtime_host import _configure_environment, DEFAULT_CREDENTIALS
        from a0v_event_complete_product_api import BUNDLE_ROOT
        from a0v_p02_current_preflight import TRUST_ROOTS
        import os
        from datetime import timedelta
        from aos_api.asset_registry.control_wiring import build_runtime_control_plane
        from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
        from aos_api.extension_runtime.consumer_connection import consumer_connection
        from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
        from aos_api.tenant_scope import TenantScope
        from aos_api.ecommerce_growth_host_ports import HostTransaction
        from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
        from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
        from aos_api.pipeline_source_selection_store import decode_selection_row
        from aos_api.pipeline_runtime_control_owner import decode_control_row
        from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
        from aos_api.ec_ingress_journal import _digest
        from a0v_snapshot_configuration_preview import build_preview
        from aos_api.asset_registry.canonical_json import canonical_sha256
        import hashlib

        _configure_environment(DEFAULT_CREDENTIALS, bundle_root=BUNDLE_ROOT, trust_roots_file=TRUST_ROOTS)
        os.environ["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] = "0"
        scope = TenantScope("org-org", "dev-project")
        plane_local = build_runtime_control_plane()
        service = plane_local.pipeline_control_factory.build(scope)
        installation_id = preview.INSTALLATION
        generation_id = preview.GENERATION
        with consumer_connection(runtime_worker_connection,
                                 dict(org_id=scope.org_id, project_id=scope.project_id)) as c:
            head = c.execute("""SELECT i.current_revision,r.state,r.lock_hash,r.overlay_revision
              FROM bundle_installation i JOIN bundle_installation_revision r
                ON (i.org_id,i.project_id,i.installation_pk,i.current_revision)=
                   (r.org_id,r.project_id,r.installation_pk,r.revision)
              WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s""",
              (*scope.key, installation_id)).fetchone()
            if (not head or head["state"] != "active"
                    or head["current_revision"] != INSTALLATION_ETAG):
                raise ValueError("current DN installation etag differs")
            ref = CurrentInstallationRef.model_validate(dict(
                installationId=installation_id, revision=INSTALLATION_ETAG,
                lockHash=head["lock_hash"], overlayRevision=head["overlay_revision"]))
            baseline = plane_local.installation_store.load_active_baseline_in_transaction(
                c, org_id=scope.org_id, project_id=scope.project_id, requested_ref=ref)
            selected, = [x for x in baseline.lock.payload.resolved if x.id == "platform.ecommerce.niushop"]
            preview_body = build_preview(service.selections._artifacts, selected, "niushop-qyh")
            binding = c.execute("""SELECT * FROM extension_runtime_binding
              WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
              (*scope.key, installation_id, generation_id)).fetchone()
            if (not binding or not binding["enabled"] or binding["operation_fence"]
                    or binding["execution_epoch"] != 3 or binding["revision"] != 6):
                raise ValueError("current DN binding differs")
            source = SourceConfigurationRevisionStore(HostTransaction(c), scope).read_current("niushop-qyh")
            now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            members = []
            for member in preview_body["members"]:
                pipeline = member["pipelineId"]
                graph = c.execute("""SELECT revision,payload FROM phase5_pipeline_graph
                  WHERE org_id=%s AND project_id=%s AND pipeline_id=%s""",
                  (*scope.key, pipeline)).fetchone()
                schedules = c.execute("""SELECT id,enabled,ingest FROM meta_schedule
                  WHERE org_id=%s AND project_id=%s AND pipeline_id=%s""",
                  (*scope.key, pipeline)).fetchall()
                if len(schedules) != 1 or schedules[0]["enabled"] is not False:
                    raise ValueError("one disabled schedule per pipeline required")
                schedule = schedules[0]
                draft = PipelineSourceSelectionDraft.model_validate(dict(
                    orgId=scope.org_id, projectId=scope.project_id, pipelineId=pipeline,
                    graphRevision=graph["revision"], graphHash=_digest(graph["payload"]),
                    installationRef=preview.wire(ref), generation=generation_id,
                    executionEpoch=3, configurationRef=binding["config_ref"],
                    packageRef=dict(publisher=selected.publisher, id=selected.id,
                                    version=selected.version, contentHash=selected.content_hash),
                    sourceId="niushop-qyh", sourceConfigurationRef=preview.wire(source.ref),
                    rowLimit=1000, timeoutSeconds=30, maxSourceCalls=1,
                    notBefore=now, expiresAt=now + timedelta(hours=4), **member["artifactRefs"]))
                service.selections._guarded(c, draft, preview.ACTOR, lambda value: True, snapshot=True)
                previous = {}
                for name, table, decode in [
                    ("selection", "pipeline_source_selection_revision", decode_selection_row),
                    ("control", "pipeline_runtime_control_revision", decode_control_row),
                ]:
                    rows = c.execute(
                        f"SELECT * FROM {table} WHERE org_id=%s AND project_id=%s AND installation_id=%s"
                        f" AND generation=%s AND pipeline_id=%s ORDER BY revision DESC LIMIT 1",
                        (*scope.key, installation_id, generation_id, pipeline)).fetchall()
                    previous[name] = preview.wire(decode(rows[0]).ref) if rows else None
                old_binding = PipelineScheduleControlOwner.read_latest(c, scope=scope, schedule_id=schedule["id"])
                previous["binding"] = preview.wire(old_binding.ref) if old_binding else None
                members.append(dict(pipelineId=pipeline, scheduleId=schedule["id"],
                                    draft=preview.wire(draft), previous=previous))
            path = "content/policies/snapshot-relationships.v1.json"
            raw = service.selections._artifacts.read_artifact(selected, path, 256 * 1024)
            policy = dict(resourceType="SnapshotRelationshipPolicy", resourceId=path,
                          revision=selected.version,
                          contentHash="sha256:" + hashlib.sha256(raw).hexdigest())
            result = dict(actor=preview.ACTOR, installationRef=preview.wire(ref),
                          generation=generation_id, preparedAt=now.isoformat(),
                          policyRef=policy, members=members, sourceReads=0, enabled=False)
            result["previewHash"] = canonical_sha256(result)
            raise Rollback()
        return result

    preview.preflight = preflight_etag5
    try:
        value = snapshot.prepare(plane)
    finally:
        preview.preflight = original
    if (value["installationRef"]["installationId"], value["generation"]) != (installation, generation):
        raise RuntimeError("exact DN preview required")
    if value["installationRef"]["revision"] != INSTALLATION_ETAG:
        raise RuntimeError("exact DN etag5 preview required")
    return {**value, "outcome": "DN_SAVED_SNAPSHOT_PREPARED"}


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
            or current["body"]["revision"] != 259 or context.get("expectedDefinitionRef") != current["ref"]
            or recovery_ref is None or recovery_ref.get("revision") != 85
            or recovery_ref.get("contentHash") != PREDECESSOR_RECOVERY_HASH):
        raise RuntimeError("exact database-backed DM recovery boundary required")
    result = service.transfer_saved_recovery(definition_id=recovery.snapshot.DEFINITION_ID,
        group_id=GROUP, actor=recovery.snapshot.ACTOR, members=members, expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref, idempotency_key=recovery.TRANSFER_KEY)
    if (result.get("ref", {}).get("revision") != 260
            or result.get("body", {}).get("installationId") != dn_successor.DN_ID
            or result.get("body", {}).get("generation") != dn_successor.DN_GENERATION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError("exact disabled DN transferred definition required")
    return {"outcome": "DN_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED", "definition": result,
            "groupId": GROUP, "inputManifestHash": MANIFEST,
            "predecessorRecoveryRef": recovery_ref, "sourceReads": 0}


def attempt_guard_module():
    import a0v_dn_attempt_guard as guard
    return guard


def _setup():
    return None, None, dn_successor.setup()


recovery.attempt_guard_module = attempt_guard_module
recovery.snapshot.baseline.setup = _setup
recovery.transfer = transfer
recovery.prepare = prepare
if __name__ == "__main__":
    recovery.main()
