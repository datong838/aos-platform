"""A content artifact can enter human review without claiming factual approval."""

from copy import deepcopy
from datetime import UTC, datetime

from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_eval_authority_store import AipEvalAuthorityNotFound
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from aos_api.aip_eval_runner import AipEvalRunner, JudgeExecution, ResolvedArtifact
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_logic_graph_models import LogicGraphSnapshot, compute_logic_graph_hash
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.aip_release_publication_models import (
    DeriveReleaseGateRequest, PublishReleaseRequest, RevokePublicationRequest,
)
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import CreateEvalContractRequest, ExactRevisionRef
from aos_api.db import connect
from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
from aos_api.tenant_scope import TenantScope

from aos_api.ecommerce_content_pre_review_eval import (
    build_content_pre_review_graph,
    execute_content_pre_review_target,
    evaluate_content_pre_review,
)


def content_input():
    return {
        "schemaVersion": "aos.eval-ecommerce-content-input/v1",
        "subjectArtifactRef": {"resourceType": "Artifact", "resourceId": "content-1",
                               "contentHash": "a" * 64},
        "content": {
            "body": "玫瑰面霜草稿；功效与库存仍待人工核实。",
            "productNames": ["玫瑰面霜"], "channels": ["微信小店"],
            "sourceArtifactRefs": [{"resourceType": "ArtifactRevision",
                                    "resourceId": f"source-{n}", "revision": 1,
                                    "contentHash": "sha256:" + "b" * 64} for n in range(4)],
            "factSourceRefs": [{"resourceType": "EvidenceBundleRevision",
                                "resourceId": "facts-1", "revision": 1,
                                "contentHash": "sha256:" + "c" * 64}],
            "constraintChecks": ["事实待人工核对"],
        },
        "caseInput": {"purpose": "human-pre-review"},
    }


def test_content_pre_review_graph_is_deterministic_and_has_no_effect_nodes():
    graph = build_content_pre_review_graph()
    assert graph.id == "ecommerce.content.pre-review.v1"
    assert {node.kind for node in graph.nodes} == {"input", "transform"}
    assert evaluate_content_pre_review(graph, content_input()) is True
    assert evaluate_content_pre_review(graph, content_input()) is True


def test_content_pre_review_rejects_empty_or_missing_human_review_inputs():
    graph = build_content_pre_review_graph()
    for field, value in (
        ("body", ""), ("productNames", []), ("channels", []),
        ("factSourceRefs", []), ("constraintChecks", []),
        ("sourceArtifactRefs", []),
    ):
        payload = content_input()
        payload["content"][field] = value
        assert evaluate_content_pre_review(graph, payload) is False, field
    missing = deepcopy(content_input())
    del missing["content"]["body"]
    assert evaluate_content_pre_review(graph, missing) is False


def test_content_pre_review_rejects_wrong_input_envelope():
    graph = build_content_pre_review_graph()
    payload = content_input()
    payload["schemaVersion"] = "wrong"
    assert evaluate_content_pre_review(graph, payload) is False


def test_content_pre_review_rejects_blank_body_bad_ref_and_non_lists():
    graph = build_content_pre_review_graph()
    for change in ("blank_body", "bad_ref", "non_list", "missing_content"):
        payload = content_input()
        if change == "blank_body":
            payload["content"]["body"] = " \n "
        elif change == "bad_ref":
            payload["subjectArtifactRef"]["resourceType"] = "EvalContractRevision"
        elif change == "non_list":
            payload["content"]["factSourceRefs"] = "source-id"
        else:
            payload.pop("content")
        assert evaluate_content_pre_review(graph, payload) is False, change


def test_content_pre_review_rejects_modified_graph_without_running_it():
    graph = build_content_pre_review_graph()
    graph.nodes[1].config["expression"] = "true"
    assert evaluate_content_pre_review(graph, content_input()) is False


def persisted_target():
    request = build_content_pre_review_graph()
    now = datetime.now(UTC)
    graph = LogicGraphSnapshot(
        id=request.id, name=request.name, description=request.description,
        status=request.status, schema_version=request.schema_version,
        revision=1, graph_hash=compute_logic_graph_hash(request),
        nodes=request.nodes, edges=request.edges,
        entry_node_ids=request.entry_node_ids,
        created_at=now, updated_at=now, persisted=True,
    )
    target = AssetRevisionRef(
        asset_type=AssetType.LOGIC_GRAPH, asset_id=graph.id,
        revision="1", content_hash=graph.graph_hash,
    )
    return graph, target


def test_content_pre_review_target_executes_exact_persisted_graph_only():
    graph, target = persisted_target()
    assert execute_content_pre_review_target(target, graph, content_input()).value is True
    payload = content_input()
    payload["content"]["factSourceRefs"] = []
    assert execute_content_pre_review_target(target, graph, payload).value is False


def test_content_pre_review_target_rejects_wrong_revision_hash_or_unpersisted_graph():
    graph, target = persisted_target()
    for bad in (
        target.model_copy(update={"revision": "2"}),
        target.model_copy(update={"content_hash": "f" * 64}),
        target.model_copy(update={"asset_id": "other-graph"}),
        graph.model_copy(update={"persisted": False}),
    ):
        if isinstance(bad, LogicGraphSnapshot):
            bad_graph, bad_target = bad, target
        else:
            bad_graph, bad_target = graph, bad
        try:
            execute_content_pre_review_target(bad_target, bad_graph, content_input())
        except ValueError:
            pass
        else:
            raise AssertionError("inexact or transient Graph target was accepted")


def test_content_pre_review_target_rejects_changed_graph_or_effect_node():
    graph, target = persisted_target()
    changed = graph.model_copy(deep=True)
    changed.nodes[1].config["expression"] = "true"
    for bad_graph in (changed, graph.model_copy(update={"status": "archived"})):
        try:
            execute_content_pre_review_target(target, bad_graph, content_input())
        except ValueError:
            pass
        else:
            raise AssertionError("changed Graph was accepted")


def test_content_pre_review_target_uses_exact_isolated_pg_snapshot():
    request = build_content_pre_review_graph()
    scope = ("org-content-eval-test", "dev-project")
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (scope[0], "内容预审隔离测试"),
        )
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) VALUES(%s,%s,%s) "
            "ON CONFLICT DO NOTHING",
            (*scope, "隔离工作区"),
        )
        conn.commit()
    store = LogicGraphStore()
    created = store.create(*scope, "test", request)
    readback = store.get(*scope, request.id)
    assert readback.graph_hash == created.graph_hash
    target = AssetRevisionRef(
        asset_type=AssetType.LOGIC_GRAPH, asset_id=readback.id,
        revision=str(readback.revision), content_hash=readback.graph_hash,
    )
    assert execute_content_pre_review_target(target, readback, content_input()).value is True


def test_content_pre_review_eval_packs_separate_governance_and_subject_cases():
    _, target = persisted_target()
    governance, subject = build_content_pre_review_eval_packs(target)
    assert governance.suite.target == subject.suite.target == target
    assert governance.suite.suite_id != subject.suite.suite_id
    assert governance.suite.gate_threshold == subject.suite.gate_threshold == 1.0
    assert len(governance.suite.cases) >= 4
    assert len(subject.suite.cases) == 1
    assert {case.kind.value for case in governance.suite.cases} >= {"positive", "negative"}
    assert subject.expected_values() == {"content-subject": True}


def test_content_pre_review_eval_packs_reject_unreviewed_target_hash():
    _, target = persisted_target()
    bad = target.model_copy(update={"content_hash": "f" * 64})
    try:
        build_content_pre_review_eval_packs(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("unreviewed Graph hash acquired an Eval pack")


def test_content_pre_review_governance_uses_formal_isolated_pg_release_path():
    scope = TenantScope("org-content-eval-authority-test", "dev-project")
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                     (scope.org_id, "内容评估发布隔离测试"))
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES(%s,%s,%s) "
                     "ON CONFLICT DO NOTHING", (*scope.key, "隔离工作区"))
        conn.commit()
    graph = LogicGraphStore().create(*scope.key, "test", build_content_pre_review_graph())
    target = AssetRevisionRef(
        asset_type=AssetType.LOGIC_GRAPH, asset_id=graph.id,
        revision=str(graph.revision), content_hash=graph.graph_hash,
    )
    governance, subject = build_content_pre_review_eval_packs(target)
    registry = AipEvalPackRegistry()
    for pack in (governance, subject):
        registry.register_dataset_revision(scope, pack.dataset, pack.manifest, actor="test")
        registry.register_suite_revision(scope, pack.suite, actor="test")
    assert registry.get_suite_revision(scope, governance.suite.suite_id, 1) == governance.suite
    try:
        registry.get_suite_revision(TenantScope("dev-org", "dev-project"),
                                    governance.suite.suite_id, 1)
    except AipEvalAuthorityNotFound:
        pass
    else:
        raise AssertionError("governance Suite leaked into isolation canary")

    def resolve(ref):
        return ResolvedArtifact(
            reference=ref, value=governance.artifacts[(ref.artifact_id, ref.revision)],
        )

    report = AipEvalRunner().run(
        scope, suite_id=governance.suite.suite_id, suite_revision=1,
        idempotency_key="content-pre-review-governance-r1", actor="test",
        resolve_artifact=resolve,
        execute_target=lambda ref, value: execute_content_pre_review_target(ref, graph, value),
        execute_judge=lambda ref, observed, wanted: JudgeExecution(
            judge=ref, passed=observed is wanted, detail_code="exact_bool_match",
        ),
    )
    assert report.gate_passed and report.passed == len(governance.suite.cases)
    release = AipReleasePublicationService()
    gate = release.derive_gate(
        scope, actor="test", request=DeriveReleaseGateRequest(
            report_id=report.report_id, report_revision=report.revision,
            report_hash=report.content_hash,
            idempotency_key="content-pre-review-governance-gate-r1",
        ),
    )
    assert gate.status.value == "passed" and gate.target == target
    published = release.publish(
        scope, actor="test", request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash="d" * 64,
            idempotency_key="content-pre-review-governance-publication-r1",
        ),
    )
    assert published.target == target and published.event_type.value == "published"
    with connect(scope) as conn:
        publication_row = conn.execute(
            "SELECT * FROM aip_publication_event WHERE org_id=%s AND project_id=%s "
            "AND event_id=%s", (*scope.key, published.event_id),
        ).fetchone()
    publication_hash = canonical_hash(
        AipProductionContractStore._publication_snapshot(publication_row)
    )
    contract_body = CreateEvalContractRequest(
        suite_ref=ExactRevisionRef(
            resource_type="EvalSuiteRevision", resource_id=subject.suite.suite_id,
            revision=subject.suite.revision, content_hash=subject.suite.content_hash,
        ),
        publication_ref=ExactRevisionRef(
            resource_type="PublicationEvent", resource_id=published.event_id,
            revision=1, content_hash=publication_hash,
        ),
        release_gate_ref=ExactRevisionRef(
            resource_type="ReleaseGateDecision", resource_id=gate.decision_id,
            revision=1, content_hash=gate.decision_hash,
        ),
        artifact_schema_ref=ResourceRef(
            resource_type="Schema", resource_id="ecommerce-readable-content-v1",
            revision="1", authority="aip",
        ),
        severity_thresholds={"critical": 1.0},
        gate_policy={
            "subjectKind": "ecommerce_content",
            "subjectInputMode": "ecommerce-readable-content/v1",
            "requiresHumanDecision": True,
        },
        return_mapping={"critical": "content_generate"},
        override_policy={"allowed": False},
    )
    contracts = AipProductionContractStore()
    draft = contracts.create_eval_contract(
        scope, "test", "content-pre-review-subject-contract-r1", contract_body,
    )
    assert draft.readiness.value == "ready"
    frozen = contracts.freeze_eval_contract(
        scope, "test", draft.contract_id, draft.version,
        "content-pre-review-subject-freeze-r1",
    )
    assert frozen.lifecycle.value == "frozen" and frozen.readiness.value == "ready"
    assert frozen.suite_ref.resource_id == subject.suite.suite_id
    assert contracts.list_eval_contracts(TenantScope("dev-org", "dev-project")).count == 0
    revoked = release.revoke(
        scope, publication_id=published.publication_id, actor="test",
        request=RevokePublicationRequest(
            reason_hash="e" * 64,
            idempotency_key="content-pre-review-governance-revoked-r1",
        ),
    )
    assert revoked.event_type.value == "revoked"
    after_revoke = contracts.get_eval_contract(scope, frozen.contract_id, frozen.revision)
    assert after_revoke.readiness.value == "blocked"
    assert {item.code for item in after_revoke.blockers} >= {"EVAL_PUBLICATION_REVOKED"}
