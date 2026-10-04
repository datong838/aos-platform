"""Disposable PostgreSQL proof that readiness can use the caller's transaction."""

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from aos_api.aip_agent_registry_contracts import (
    OperationalBindingDependencies,
    VersionedAssetRef,
)
from aos_api.aip_binding_readiness_service import AipBindingReadinessService
from aos_api.aip_contracts import ResourceRef
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope


def test_readiness_uses_uncommitted_exact_catalog_on_caller_transaction():
    dsn = get_dsn()
    dbname = conninfo_to_dict(dsn)["dbname"]
    assert dbname.startswith("aos_test_") and dbname.endswith("_ti4_test")
    capability_id = "b45.transaction." + uuid4().hex
    content_hash = "a" * 64
    ref = VersionedAssetRef(
        asset_type="CapabilityRevision", asset_id=capability_id,
        revision=1, content_hash=content_hash,
    )
    scope = TenantScope("org-org", "dev-project")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        try:
            conn.execute("""INSERT INTO aip_capability_revision(
                capability_id,revision,display_name,lifecycle,aliases,input_schema_ref,
                output_schema_ref,risk_level,required_data_refs,required_tool_refs,
                required_capability_refs,memory_policy_ref,handoff_policy_ref,
                effect_review_schema_ref,license_policy_ref,readiness_policy_ref,
                readiness,readiness_reasons,source_ref,source_license,content_hash,
                created_by)
                VALUES(%s,1,'test-only','published','[]','{}','{}','low',
                '[]','[]','[]','{}','{}','{}','{}','{}','unknown','[]',
                '{}','test-only',%s,'b45-test-only')""",
                (capability_id, content_hash))
            independent = AipBindingReadinessService().evaluate_capability(
                scope, ref, OperationalBindingDependencies(),
                evaluated_at=datetime.now(UTC),
            )
            assert "CAPABILITY_REVISION_UNAVAILABLE" in independent.reasons

            bound = AipBindingReadinessService.for_transaction(conn).evaluate_capability(
                scope, ref, OperationalBindingDependencies(),
                evaluated_at=datetime.now(UTC),
            )
            assert "CAPABILITY_REVISION_UNAVAILABLE" not in bound.reasons
            assert bound.readiness.value == "blocked"
            still_uncommitted = AipBindingReadinessService().evaluate_capability(
                scope, ref, OperationalBindingDependencies(),
                evaluated_at=datetime.now(UTC),
            )
            assert "CAPABILITY_REVISION_UNAVAILABLE" in still_uncommitted.reasons
        finally:
            conn.rollback()


def test_license_evidence_and_revocation_share_final_readiness_transaction():
    dsn = get_dsn()
    dbname = conninfo_to_dict(dsn)["dbname"]
    assert dbname.startswith("aos_test_") and dbname.endswith("_ti4_test")
    scope = TenantScope("org-org", "dev-project")
    evidence_id = "b68.license." + uuid4().hex
    capability = VersionedAssetRef(
        asset_type="CapabilityRevision", asset_id="b68.missing." + uuid4().hex,
        revision=1, content_hash="a" * 64,
    )
    dependencies = OperationalBindingDependencies(license_evidence_refs=[ResourceRef(
        resource_type="EvidenceBundleRevision", resource_id=evidence_id,
        revision="1", authority="test-only",
    )])
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        try:
            conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') "
                         "ON CONFLICT DO NOTHING")
            conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) "
                         "VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
            conn.execute("""INSERT INTO aip_evidence_bundle_revision
                (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
                 item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
                 license_summary,content_hash,lifecycle,created_by)
                VALUES(%s,%s,%s,1,'{}'::jsonb,'[]'::jsonb,NOW(),'[]'::jsonb,
                       'complete','[]'::jsonb,'[]'::jsonb,'[]'::jsonb,'fresh',
                       '{}'::jsonb,'{"license":"test-only"}'::jsonb,%s,
                       'frozen','test-only')""", (*scope.key, evidence_id, "b" * 64))
            checked_at = datetime.now(UTC)
            outside = AipBindingReadinessService().evaluate_capability(
                scope, capability, dependencies, evaluated_at=checked_at)
            assert "LICENSE_EVIDENCE_MISSING" in outside.reasons
            bound = AipBindingReadinessService.for_transaction(conn)
            before_revoke = bound.evaluate_capability(
                scope, capability, dependencies, evaluated_at=checked_at)
            assert "LICENSE_EVIDENCE_MISSING" not in before_revoke.reasons
            assert before_revoke.readiness.value == "blocked"
            conn.execute("""INSERT INTO aip_evidence_bundle_revoke_event
                (org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor)
                VALUES(%s,%s,%s,%s,1,%s,'test-only','test-only')""",
                (*scope.key, "b68-revoke-" + uuid4().hex, evidence_id, "b" * 64))
            after_revoke = bound.evaluate_capability(
                scope, capability, dependencies, evaluated_at=checked_at)
            assert "LICENSE_EVIDENCE_MISSING" in after_revoke.reasons
        finally:
            conn.rollback()
