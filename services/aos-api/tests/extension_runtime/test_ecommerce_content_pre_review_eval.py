"""A content artifact can enter human review without claiming factual approval."""

from copy import deepcopy

from aos_api.ecommerce_content_pre_review_eval import (
    build_content_pre_review_graph,
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
