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
