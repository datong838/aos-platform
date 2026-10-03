"""An exact frozen EvidenceBundle stops serving bindings after revocation."""

from uuid import uuid4

from psycopg.conninfo import conninfo_to_dict

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_binding_readiness_service import PostgresBindingDependencyAuthority
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


def test_evidence_bundle_revocation_is_visible_to_binding_readiness():
    database = conninfo_to_dict(get_dsn())["dbname"]
    assert database.startswith("aos_test_") and database.endswith("_ti4_test")
    scope = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    bundle_id = f"s3owal-{uuid4().hex}"
    content_hash = "a" * 64
    evidence = VersionedAssetRef(
        asset_type="EvidenceBundleRevision", asset_id=bundle_id,
        revision=1, content_hash=content_hash,
    )

    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','隔离测试组织') ON CONFLICT DO NOTHING")
        conn.execute("""INSERT INTO twa_workspace(org_id,project_id,name)
            VALUES('org-org','dev-project','隔离测试工作区') ON CONFLICT DO NOTHING""")
        conn.commit()
    with connect(scope) as conn:
        conn.execute("""INSERT INTO aip_evidence_bundle_revision
            (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
             item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
             license_summary,content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,1,'{}'::jsonb,'[]'::jsonb,NOW(),'[]'::jsonb,
                   'complete','[]'::jsonb,'[]'::jsonb,'[]'::jsonb,'fresh',
                   '{}'::jsonb,'{}'::jsonb,%s,'frozen','test-only')""",
            (*scope.key, bundle_id, content_hash),
        )
        conn.commit()

    authority = PostgresBindingDependencyAuthority()
    assert authority.exact_assets_available(scope, [evidence])
    assert not authority.exact_assets_available(canary, [evidence])

    with connect(scope) as conn:
        conn.execute("""INSERT INTO aip_evidence_bundle_revoke_event
            (org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,1,%s,'test-only-revocation','test-only')""",
            (*scope.key, f"revoke-{uuid4().hex}", bundle_id, content_hash),
        )
        conn.commit()
    assert not authority.exact_assets_available(scope, [evidence])
