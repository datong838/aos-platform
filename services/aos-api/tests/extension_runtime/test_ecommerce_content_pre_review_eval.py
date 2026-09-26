"""A content artifact can enter human review without claiming factual approval."""

from copy import deepcopy
from datetime import UTC, datetime

from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_logic_graph_models import LogicGraphSnapshot, compute_logic_graph_hash
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.db import connect

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
