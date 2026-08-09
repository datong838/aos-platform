from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.ontology_explorer_contracts import (
    ONTOLOGY_EXPLORER_ERROR_CODES,
    EvidenceRefDTO,
    ExplorationCreateDTO,
    GraphEdgeDTO,
    GraphQueryDTO,
    GraphSnapshotDTO,
    KnowledgeSubjectRefDTO,
    LinkRefDTO,
    ObjectSetCreateDTO,
    TaskRefDTO,
)


def test_exploration_create_forbids_client_tenant_scope() -> None:
    with pytest.raises(ValidationError):
        ExplorationCreateDTO.model_validate(
            {
                "name": "订单风险探索",
                "objectType": "Order",
                "org_id": "org-org",
                "workspace_id": "dev-project",
            }
        )


def test_object_set_v1_rejects_cross_type_items() -> None:
    with pytest.raises(ValidationError, match="OBJECT_SET_TYPE_MISMATCH"):
        ObjectSetCreateDTO.model_validate(
            {
                "name": "混合对象",
                "objectType": "Order",
                "items": [
                    {"objectType": "Order", "objectId": "1"},
                    {"objectType": "Payment", "objectId": "12"},
                ],
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("hops", 0), ("hops", 6), ("maxNodes", 0), ("maxNodes", 501)],
)
def test_graph_query_enforces_frozen_limits(field: str, value: int) -> None:
    payload = {
        "seeds": [{"objectType": "Order", "objectId": "1"}],
        "hops": 1,
        "maxNodes": 100,
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        GraphQueryDTO.model_validate(payload)


def test_graph_snapshot_requires_authority_and_scope_metadata() -> None:
    snapshot = GraphSnapshotDTO.model_validate(
        {
            "scope": {"orgId": "org-org", "workspaceId": "dev-project"},
            "sourceAuthority": "ecom_authoritative",
            "schemaEtag": "composed-schema-v1:sha256:abc",
            "snapshot": {"asOf": "2026-08-09T00:00:00Z", "watermark": "42"},
            "nodes": [{"key": "Order:1", "objectType": "Order", "objectId": "1", "label": "1", "depth": 0, "masked": True}],
            "edges": [],
            "page": {"truncated": False, "nextCursor": None},
            "limits": {"maxNodes": 500, "maxHops": 5},
        }
    )
    assert snapshot.scope.orgId == "org-org"
    assert snapshot.sourceAuthority == "ecom_authoritative"


def test_error_code_set_is_frozen() -> None:
    assert ONTOLOGY_EXPLORER_ERROR_CODES == (
        "TENANT_SCOPE_REQUIRED",
        "TENANT_SCOPE_FORBIDDEN",
        "EXPLORATION_SHARE_FORBIDDEN",
        "EXPLORATION_NOT_FOUND",
        "IDEMPOTENCY_CONFLICT",
        "OBJECT_REFERENCE_UNSTABLE",
        "REVISION_CONFLICT",
        "GRAPH_QUERY_TOO_LARGE",
        "GRAPH_QUERY_INVALID",
        "OBJECT_SET_TYPE_MISMATCH",
        "GRAPH_QUERY_RATE_LIMITED",
        "GRAPH_AUTHORITY_UNAVAILABLE",
        "EXPLORATION_ARCHIVE_REQUIRED",
    )


def test_common_refs_freeze_wire_names_lengths_and_unknown_field_rejection() -> None:
    object_ref = {"objectType": "Order", "objectId": "niushop:1:1"}
    link = LinkRefDTO.model_validate(
        {"relationType": "Order.hasPayment", "source": object_ref, "target": {"objectType": "Payment", "objectId": "niushop:1:9"}}
    )
    assert link.source.objectType == "Order"
    assert TaskRefDTO.model_validate({"taskId": "task-1", "revision": 1}).revision == 1
    assert EvidenceRefDTO.model_validate({"evidenceId": "ev-1", "revision": 2}).revision == 2
    assert KnowledgeSubjectRefDTO.model_validate(
        {"subjectType": "object_instance", "subjectId": "Order:niushop:1:1", "objectRef": object_ref}
    ).objectRef == link.source

    with pytest.raises(ValidationError):
        LinkRefDTO.model_validate({"relationType": "x", "source": object_ref, "target": object_ref, "orgId": "evil"})
    with pytest.raises(ValidationError):
        TaskRefDTO.model_validate({"taskId": "x" * 513})


def test_graph_query_rejects_response_scope_and_watermark_injection() -> None:
    payload = {
        "seeds": [{"objectType": "Order", "objectId": "1"}],
        "graphDomains": ["domain"],
        "schemaEtag": "forged",
        "watermark": "forged",
        "riskLevel": "low",
        "requiresApproval": False,
    }
    with pytest.raises(ValidationError):
        GraphQueryDTO.model_validate(payload)


def test_graph_edge_fails_closed_for_unknown_authority_and_incomplete_inference() -> None:
    base = {
        "key": "Order:1->Payment:9",
        "relationType": "Order.hasPayment",
        "source": "Order:1",
        "target": "Payment:9",
        "direction": "out",
        "graphDomain": "domain",
        "sourceRevision": "run:42",
        "validity": {"validFrom": "2026-08-09T00:00:00Z", "validUntil": None},
        "evidenceRefs": [{"evidenceId": "ev-1", "revision": 1}],
    }
    authoritative = GraphEdgeDTO.model_validate({**base, "edgeAuthority": "authoritative"})
    assert authoritative.graphDomain == "domain"
    assert authoritative.evidenceRefs[0].evidenceId == "ev-1"

    with pytest.raises(ValidationError):
        GraphEdgeDTO.model_validate({**base, "edgeAuthority": "trusted_by_client"})
    with pytest.raises(ValidationError, match="inferred edges require"):
        GraphEdgeDTO.model_validate({**base, "edgeAuthority": "inferred"})
    inferred = GraphEdgeDTO.model_validate(
        {**base, "edgeAuthority": "inferred", "confidence": 0.8, "inferenceBasis": "rule:r-1"}
    )
    assert inferred.confidence == 0.8


def test_graph_snapshot_v1_remains_backward_compatible_and_accepts_explicit_domain() -> None:
    legacy = GraphSnapshotDTO.model_validate(
        {
            "scope": {"orgId": "org-org", "workspaceId": "dev-project"},
            "sourceAuthority": "ecom_authoritative",
            "schemaEtag": "composed-schema-v1:sha256:abc",
            "snapshot": {"asOf": "2026-08-09T00:00:00Z", "watermark": "42"},
            "nodes": [],
            "edges": [],
            "page": {"truncated": False},
            "limits": {"maxNodes": 500, "maxHops": 5},
        }
    )
    assert legacy.graphDomain is None
    expanded = legacy.model_copy(update={"graphDomain": "domain"})
    assert GraphSnapshotDTO.model_validate(expanded.model_dump()).graphDomain == "domain"
    with pytest.raises(ValidationError):
        GraphSnapshotDTO.model_validate({**legacy.model_dump(), "sourceAuthority": "client_trusted"})


def test_openapi_contains_ua1_common_contract_components() -> None:
    from aos_api.main import create_app

    schemas = create_app().openapi()["components"]["schemas"]
    for name in (
        "ObjectRefDTO",
        "LinkRefDTO",
        "KnowledgeSubjectRefDTO",
        "TaskRefDTO",
        "EvidenceRefDTO",
        "GraphSnapshotDTO",
    ):
        assert name in schemas
