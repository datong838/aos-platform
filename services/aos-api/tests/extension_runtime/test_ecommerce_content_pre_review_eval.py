"""A content artifact can enter human review without claiming factual approval."""

import json
from copy import deepcopy
from datetime import UTC, datetime
import pytest

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
from aos_api.ecommerce_content_pre_review_authority import require_current_content_pre_review_gate
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
    with connect(scope) as conn:
        for pack in (governance, subject):
            conn.execute(
                """INSERT INTO aip_artifact
                   (org_id,project_id,artifact_id,artifact_type,content_hash,
                    content_ref,source,created_by)
                   VALUES (%s,%s,%s,'eval_dataset_snapshot',%s,%s,'{}'::jsonb,'test'),
                          (%s,%s,%s,'redaction_receipt',%s,%s,%s::jsonb,'test')""",
                (*scope.key, pack.manifest.source_id, pack.manifest.source_hash,
                 f"test-only://{pack.manifest.source_id}",
                 *scope.key, pack.manifest.redaction_receipt.artifact_id,
                 pack.manifest.redaction_receipt.content_hash,
                 f"test-only://{pack.manifest.redaction_receipt.artifact_id}",
                 json.dumps({"sourceArtifactRef": {
                     "artifactId": pack.manifest.source_id,
                     "artifactType": "eval_dataset_snapshot", "revision": "1",
                     "contentHash": pack.manifest.source_hash}})),
            )
        conn.commit()
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
    with connect(scope) as conn:
        exact_gate = require_current_content_pre_review_gate(conn, scope)
    assert (exact_gate.resource_type, exact_gate.resource_id, exact_gate.revision,
            exact_gate.content_hash) == (
        "EvalContractRevision", frozen.contract_id, frozen.revision, frozen.content_hash,
    )

    class FaultCursor:
        def __init__(self, cursor, fault):
            self.cursor, self.fault = cursor, fault

        def fetchone(self):
            row = self.cursor.fetchone()
            return self.fault(row) if row is not None else row

        def fetchall(self):
            rows = self.cursor.fetchall()
            return self.fault(rows)

    class FaultTransaction:
        def __init__(self, conn, kind):
            self.conn, self.kind = conn, kind

        def execute(self, query, params=None):
            cursor = self.conn.execute(query, params)
            if self.kind == "duplicate" and "FROM aip_eval_contract_head h" in query:
                return FaultCursor(cursor, lambda rows: [*rows, dict(rows[0])])
            if self.kind == "subject_suite" and "SELECT * FROM aip_eval_suite_revision" in query and (
                params and params[-2] == subject.suite.suite_id
            ):
                return FaultCursor(cursor, lambda row: {
                    **row, "target_ref": {**row["target_ref"], "contentHash": "f" * 64},
                })
            if self.kind == "gate_target" and "SELECT * FROM aip_release_gate_decision" in query:
                return FaultCursor(cursor, lambda row: {
                    **row, "target_ref": {**row["target_ref"], "contentHash": "f" * 64},
                })
            if self.kind == "publication_target" and "SELECT * FROM aip_publication_event" in query:
                return FaultCursor(cursor, lambda row: {
                    **row, "target_ref": {**row["target_ref"], "contentHash": "f" * 64},
                })
            if self.kind == "graph_hash" and "FROM aip_logic_graph WHERE" in query:
                return FaultCursor(cursor, lambda row: {**row, "graph_hash": "f" * 64})
            if self.kind == "contract_severity" and "SELECT * FROM aip_eval_contract_revision WHERE" in query:
                return FaultCursor(cursor, lambda row: {
                    **row, "severity_thresholds": {"critical": 0.5},
                })
            if self.kind == "expired_clock" and "SELECT clock_timestamp() AS now" in query:
                return FaultCursor(cursor, lambda row: {
                    "now": gate.expires_at + (gate.expires_at - gate.decided_at),
                })
            return cursor

    for fault in (
        "duplicate", "subject_suite", "gate_target", "publication_target",
        "graph_hash", "contract_severity", "expired_clock",
    ):
        with connect(scope) as conn, pytest.raises(ValueError):
            require_current_content_pre_review_gate(FaultTransaction(conn, fault), scope)
    with connect(TenantScope("dev-org", "dev-project")) as conn:
        try:
            require_current_content_pre_review_gate(conn, TenantScope("dev-org", "dev-project"))
        except ValueError:
            pass
        else:
            raise AssertionError("isolation canary acquired a content Eval gate")
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
    with connect(scope) as conn:
        try:
            require_current_content_pre_review_gate(conn, scope)
        except ValueError:
            pass
        else:
            raise AssertionError("revoked publication still authorized Plan gate")
