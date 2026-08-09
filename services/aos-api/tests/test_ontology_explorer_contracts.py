from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.ontology_explorer_contracts import (
    ONTOLOGY_EXPLORER_ERROR_CODES,
    ExplorationCreateDTO,
    GraphQueryDTO,
    GraphSnapshotDTO,
    ObjectSetCreateDTO,
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

