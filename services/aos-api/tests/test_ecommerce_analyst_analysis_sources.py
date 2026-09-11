from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import os

import pytest

import aos_api.ecommerce_analyst_analysis_sources as module
from aos_api.tenant_scope import TenantScope
from aos_api.aip_production_contracts import ExactRevisionRef, ResolveEvidenceDisclosureRequest

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime.now(timezone.utc)


def setup(monkeypatch):
    ref = lambda kind, name: ExactRevisionRef(resourceType=kind, resourceId=name, revision=1, contentHash="a" * 64)
    items = [ref("Evidence", "one"), ref("Evidence", "two")]
    bundle_ref = ref("EvidenceBundleRevision", "bundle")
    tenant = SimpleNamespace(org_id=SCOPE.org_id, project_id=SCOPE.project_id)
    bundle = SimpleNamespace(tenant=tenant, bundle_id="bundle", revision=1, content_hash="a" * 64, lifecycle="frozen", coverage="complete", freshness="fresh", revoked=False,
        cutoff_at=NOW, brief_ref=ref("TaskBriefRevision", "brief"), item_refs=items)
    brief = SimpleNamespace(tenant=tenant, task_id="task", brief_id="brief", revision=1, content_hash="a" * 64, lifecycle="frozen")
    grants = [dict(decisionId="grant-" + x.resource_id, request=dict(evidenceRef=x.model_dump(mode="json", by_alias=True), purpose="source", requestedLevel="l3", taskId="task")) for x in reversed(items)]
    request = module.AnalysisBundleSourceRequest(bundleRef=bundle_ref.model_dump(mode="json", by_alias=True), grants=grants)
    state = SimpleNamespace(reads=[], denied=False)
    connection = object()
    class Owner:
        def get_evidence_bundle(self, scope, *args, **kwargs):
            assert scope == SCOPE and kwargs["conn"] is connection
            return bundle
        def get_brief(self, scope, *args, **kwargs):
            assert kwargs["conn"] is connection
            return brief
        def read_disclosed_evidence_source(self, conn, scope, actor, decision_id, body, **kwargs):
            assert conn is connection and scope == SCOPE and actor == "actor"
            if state.denied: raise ValueError("disclosure denied")
            state.reads.append(body.evidence_ref.resource_id)
            return dict(evidenceRef=body.evidence_ref.model_dump(mode="json", by_alias=True), disclosureRef={"resourceId": decision_id}, expiresAt=(NOW + timedelta(minutes=5)).isoformat(), payload={"fact": body.evidence_ref.resource_id})
    monkeypatch.setattr(module, "AipProductionContractStore", Owner)
    kwargs = dict(conn=connection, scope=SCOPE, task_id="task", actor="actor", request=request, markings=["internal", "secret"], now=NOW, max_source_age=timedelta(days=1), max_bytes=10000)
    return kwargs, bundle, brief, state


def test_material_is_complete_and_ordered_by_bundle_not_grants(monkeypatch):
    kwargs, _, _, state = setup(monkeypatch)
    result = module.read_analysis_bundle(**kwargs)
    assert state.reads == ["one", "two"]
    assert [x["payload"]["fact"] for x in result["items"]] == ["one", "two"]


@pytest.mark.parametrize("problem", ["tenant", "bundle_hash", "revoked", "coverage", "stale", "future", "brief_task", "brief_hash", "brief_lifecycle", "missing", "duplicate", "wrong_task", "wrong_purpose", "wrong_level", "unknown_evidence", "oversize", "denied"])
def test_unusable_or_incomplete_material_is_not_returned(monkeypatch, problem):
    kwargs, bundle, brief, state = setup(monkeypatch)
    if problem == "tenant": bundle.tenant.org_id = "other"
    elif problem == "bundle_hash": bundle.content_hash = "b" * 64
    elif problem == "revoked": bundle.revoked = True
    elif problem == "coverage": bundle.coverage = "partial"
    elif problem == "stale": kwargs["now"] = NOW + timedelta(days=2)
    elif problem == "future": kwargs["now"] = NOW - timedelta(seconds=1)
    elif problem == "brief_task": brief.task_id = "other"
    elif problem == "brief_hash": brief.content_hash = "b" * 64
    elif problem == "brief_lifecycle": brief.lifecycle = "draft"
    elif problem == "missing": kwargs["request"].grants.pop()
    elif problem == "duplicate": kwargs["request"].grants[0] = kwargs["request"].grants[1]
    elif problem == "wrong_task": kwargs["request"].grants[0].request.task_id = "other"
    elif problem == "wrong_purpose": kwargs["request"].grants[0].request.purpose = "audit"
    elif problem == "wrong_level": kwargs["request"].grants[0].request.requested_level = "l2"
    elif problem == "unknown_evidence": kwargs["request"].grants[0].request.evidence_ref.resource_id = "other"
    elif problem == "oversize": kwargs["max_bytes"] = 1
    elif problem == "denied": state.denied = True
    with pytest.raises(ValueError): module.read_analysis_bundle(**kwargs)
    if problem not in {"oversize", "denied"}: assert state.reads == []


@pytest.mark.skipif(os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database opt-in required")
def test_real_bundle_and_disclosure_owner_produce_bound_material():
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, insert
    from test_aip_taor_lease_adapter import running_run
    from aos_api.aip_task_store import AipTaskStore
    from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
    from aos_api.aip_production_contracts import BuildEvidenceBundleRequest, RevokeEvidenceRequest
    with disposable_database() as connect:
        run = running_run(AipTaskStore(connect_factory=connect))
        payload = {"facts": ["repeat_rate"], "values": {"repeat_rate": 0.2}, "marking": ["internal"]}
        with connect(SCOPE) as conn:
            insert(conn, "aip_task_brief_head", brief_id="material-brief", task_id=run.task_id, current_revision=1)
            insert(conn, "aip_task_brief_revision", brief_id="material-brief", task_id=run.task_id, revision=1, brief_type="analysis", schema_ref=dict(resourceType="Schema", resourceId="fixture", revision="1", authority="postgresql"), spec={}, content_hash="c" * 64, lifecycle="frozen", created_by="actor")
            insert(conn, "aip_evidence", evidence_id="material-evidence", run_id=run.id, evidence_type="query", subject_ref={}, source_type="database", source_ref="synthetic", observed_at=NOW, freshness_at=NOW, content_hash=canonical_hash(payload), payload=payload, created_by="actor")
        owner = AipProductionContractStore(connect)
        evidence = dict(resourceType="Evidence", resourceId="material-evidence", revision=1, contentHash=canonical_hash(payload))
        bundle = owner.build_evidence_bundle(SCOPE, "actor", "material-bundle", BuildEvidenceBundleRequest(briefRef=dict(resourceType="TaskBriefRevision", resourceId="material-brief", revision=1, contentHash="c" * 64), cutoffAt=NOW, itemRefs=[evidence], requiredFactIds=["repeat_rate"], marking=["internal"]))
        body = ResolveEvidenceDisclosureRequest(evidenceRef=evidence, purpose="source", requestedLevel="l3", taskId=run.task_id)
        disclosure = owner.resolve_evidence_disclosure(SCOPE, "actor", "material-disclosure", body, markings=["internal", "secret"])
        assert disclosure.status.value == "allowed"
        request = module.AnalysisBundleSourceRequest(bundleRef=dict(resourceType="EvidenceBundleRevision", resourceId=bundle.bundle_id, revision=1, contentHash=bundle.content_hash), grants=[dict(decisionId=disclosure.decision_id, request=body)])
        kwargs = dict(scope=SCOPE, task_id=run.task_id, actor="actor", request=request, markings=["internal", "secret"], now=NOW, max_source_age=timedelta(days=1), max_bytes=10000)
        with connect(SCOPE) as conn:
            material = module.read_analysis_bundle(conn=conn, **kwargs)
            assert material["items"][0]["payload"] == payload
            assert material["items"][0]["evidenceRef"] == evidence
        owner.revoke_evidence(SCOPE, "actor", "material-evidence", "material-revoke", RevokeEvidenceRequest(expectedContentHash=canonical_hash(payload), reason="synthetic withdrawal"))
        with connect(SCOPE) as conn:
            with pytest.raises((ValueError, RuntimeError)):
                module.read_analysis_bundle(conn=conn, **kwargs)
