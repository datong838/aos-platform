"""Real Owner/approval/source-reader integration, not natural Handoff acceptance."""
import os
from uuid import uuid4
from psycopg.conninfo import conninfo_to_dict
import pytest
from aos_api.db import connect
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_growth_plan_approval import ApproveGrowthPlanRequest, EcommerceAnalystGrowthPlanApprovalService
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_approval import plan
SCOPE = TenantScope("org-org", "dev-project")

def external_ref(ref):
    return dict(ref.model_dump(mode="json", by_alias=True), contentHash="sha256:" + ref.content_hash)

def read(ref, scope=SCOPE):
    with connect(scope) as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        return ReviewAdvanceHostService._revalidate_growth_plan(transaction=HostTransaction(conn), scope=scope, command={"growthPlanRef": ref})

def test_original_approval_successor_matches_handoff_source_and_replay():
    database = conninfo_to_dict(os.environ["AOS_DATABASE_URL"])["dbname"]
    assert database.startswith("aos_test_") and database.endswith("_ti4_test")
    identity = "gwc-plan-" + uuid4().hex
    # Explicit fixture only, never claimed as real provider generation.
    with connect(SCOPE) as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated fixture') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated fixture') ON CONFLICT DO NOTHING")
    draft = plan(plan_id=identity)
    draft = draft.model_copy(update={"content_hash": canonical_hash(draft.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
    owner = EcommerceAnalystAuthorityStore()
    draft_ref = owner.publish_plan(SCOPE, draft.created_by, identity + ":draft", draft, expected_version=0)
    with pytest.raises(ValueError, match="APPROVED"):
        read(external_ref(draft_ref))
    service = EcommerceAnalystGrowthPlanApprovalService(owner)
    request = ApproveGrowthPlanRequest(draftRef=draft_ref)
    approved = service.approve(SCOPE, identity, request, expected_version=1, idempotency_key=identity + ":approve", actor="fixture-reviewer")
    reread = read(external_ref(approved.approved_ref))
    assert reread.prior_ref == draft_ref and reread.revision == 2
    assert reread.objective == draft.objective and reread.items == draft.items
    assert not owner.is_current_plan(SCOPE, draft_ref)
    assert owner.get_plan_exact(SCOPE, draft_ref) == draft
    replay = service.approve(SCOPE, identity, request, expected_version=1, idempotency_key=identity + ":approve", actor="fixture-reviewer")
    assert replay.replayed and replay.approved_ref == approved.approved_ref
    assert read(external_ref(replay.approved_ref)) == reread
    for bad_scope, bad_ref in [(TenantScope("dev-org", "dev-project"), external_ref(approved.approved_ref)), (SCOPE, dict(external_ref(approved.approved_ref), contentHash="sha256:" + "0" * 64)), (SCOPE, external_ref(draft_ref))]:
        with pytest.raises(ValueError, match="current exact"):
            read(bad_ref, bad_scope)
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_growth_plan_revision WHERE org_id=%s AND project_id=%s AND plan_id=%s", (*SCOPE.key, identity)).fetchone()["n"] == 2
        assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_authority_receipt WHERE org_id=%s AND project_id=%s AND operation='analyst.growth_plan_publish' AND result_ref->>'resourceId'=%s", (*SCOPE.key, identity)).fetchone()["n"] == 2
