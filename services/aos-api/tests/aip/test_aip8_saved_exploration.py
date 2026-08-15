from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aos_api import ontology_exploration_assets as assets
from aos_api.aip_analyst_contracts import QuerySourceRef, SemanticQueryRequest
from aos_api.aip_contracts import ResourceRef
from aos_api.errors import ApiError
from aos_api.ontology_exploration_assets import append_asset, get_asset, list_assets
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _bound_exploration(expires_at: datetime) -> dict[str, object]:
    cutoff = datetime.now(UTC)
    query = SemanticQueryRequest(object_type="Order", cutoff_at=cutoff)
    result_ref = ResourceRef(
        resource_type="QueryResultRevision",
        resource_id=_id("query"),
        revision="1",
        authority="aip-analyst",
    )
    source = QuerySourceRef(
        ref=ResourceRef(
            resource_type="ObjectTypeRevision",
            resource_id="Order",
            revision="12",
            authority="ontology",
        ),
        content_hash="a" * 64,
        cutoff_at=cutoff,
        freshness="fresh",
        markings=["public"],
    )
    return {
        "name": "订单真实探索",
        "objectType": "Order",
        "viewMode": "table",
        "visibility": "workspace",
        "query": {},
        "columns": [{"key": "orderNo"}],
        "graph": {},
        "analystQuery": query.model_dump(mode="json", by_alias=True),
        "resultRef": result_ref.model_dump(mode="json", by_alias=True),
        "cutoffAt": cutoff.isoformat(),
        "sourceRefs": [source.model_dump(mode="json", by_alias=True)],
        "sort": [{"field": "createdAt", "direction": "desc"}],
        "share": {"scope": "workspace", "expiresAt": expires_at.isoformat()},
    }


def test_saved_analyst_exploration_keeps_exact_refs_and_expiring_share(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    asset_id = _id("exp")
    created, _ = append_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        payload=_bound_exploration(expires_at),
        expected_revision=0,
        idempotency_key=_id("create"),
        actor="user:owner",
    )
    payload = created["payload"]
    assert payload["resultRef"]["revision"] == "1"
    assert payload["sourceRefs"][0]["ref"]["revision"] == "12"
    assert "rows" not in payload
    assert get_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        actor="user:viewer",
    ) is not None

    monkeypatch.setattr(assets, "_now", lambda: expires_at + timedelta(seconds=1))
    assert get_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        actor="user:viewer",
    ) is None
    assert get_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        actor="user:owner",
    ) is not None
    assert all(
        item["id"] != asset_id
        for item in list_assets(
            SCOPE,
            kind="exploration",
            actor="user:viewer",
        )
    )
    assert get_asset(
        TenantScope("dev-org", "dev-project"),
        kind="exploration",
        asset_id=asset_id,
        actor="user:owner",
    ) is None


def test_result_ref_requires_exact_sources() -> None:
    payload = _bound_exploration(datetime.now(UTC) + timedelta(hours=1))
    payload["sourceRefs"] = []
    with pytest.raises(ValidationError, match="saved resultRef requires exact sourceRefs"):
        assets.ExplorationAssetPayload.model_validate(payload)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload["resultRef"].update({"authority": "local"}),
            "resultRef must be an exact AIP Analyst result revision",
        ),
        (
            lambda payload: payload["resultRef"].update({"revision": None}),
            "resultRef must be an exact AIP Analyst result revision",
        ),
        (
            lambda payload: payload.update(
                {"cutoffAt": (datetime.now(UTC) + timedelta(days=1)).isoformat()}
            ),
            "exploration cutoffAt must match analystQuery cutoffAt",
        ),
        (
            lambda payload: payload["query"].update({"rows": [{"id": "copied"}]}),
            "saved exploration must reference results, not copy result data",
        ),
    ],
)
def test_saved_exploration_rejects_authority_or_payload_drift(
    mutate,
    message: str,
) -> None:
    payload = _bound_exploration(datetime.now(UTC) + timedelta(hours=1))
    mutate(payload)
    with pytest.raises(ValidationError, match=message):
        assets.ExplorationAssetPayload.model_validate(payload)


def test_non_owner_cannot_revise_workspace_share() -> None:
    asset_id = _id("owner-only")
    created, _ = append_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        payload=_bound_exploration(datetime.now(UTC) + timedelta(hours=1)),
        expected_revision=0,
        idempotency_key=_id("owner-create"),
        actor="user:owner",
    )
    with pytest.raises(ApiError) as exc_info:
        append_asset(
            SCOPE,
            kind="exploration",
            asset_id=asset_id,
            payload=created["payload"],
            expected_revision=1,
            idempotency_key=_id("viewer-write"),
            actor="user:viewer",
        )
    assert exc_info.value.code == "EXPLORATION_SHARE_FORBIDDEN"


def test_share_and_unshare_are_revisioned_idempotent_http_commands(
    client,
    auth_headers,
) -> None:
    create_key = _id("create-http")
    created = client.post(
        "/v1/ontology/explorations",
        headers={**auth_headers, "Idempotency-Key": create_key},
        json={
            "name": "订单探索",
            "objectType": "Order",
            "viewMode": "table",
            "visibility": "private",
        },
    )
    assert created.status_code == 200, created.text
    asset_id = created.json()["id"]
    share_key = _id("share-http")
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    share_headers = {
        **auth_headers,
        "Idempotency-Key": share_key,
        "If-Match": created.headers["etag"],
    }
    shared = client.post(
        f"/v1/ontology/explorations/{asset_id}/share",
        headers=share_headers,
        json={"expiresAt": expires_at.isoformat()},
    )
    assert shared.status_code == 200, shared.text
    assert shared.json()["revision"] == 2
    assert shared.json()["payload"]["share"]["scope"] == "workspace"
    replay = client.post(
        f"/v1/ontology/explorations/{asset_id}/share",
        headers=share_headers,
        json={"expiresAt": expires_at.isoformat()},
    )
    assert replay.status_code == 200
    assert replay.json() == shared.json()
    drift = client.post(
        f"/v1/ontology/explorations/{asset_id}/share",
        headers=share_headers,
        json={"expiresAt": (expires_at + timedelta(hours=1)).isoformat()},
    )
    assert drift.status_code == 409
    assert drift.json()["code"] == "IDEMPOTENCY_CONFLICT"

    unshared = client.post(
        f"/v1/ontology/explorations/{asset_id}/unshare",
        headers={
            **auth_headers,
            "Idempotency-Key": _id("unshare-http"),
            "If-Match": shared.headers["etag"],
        },
    )
    assert unshared.status_code == 200, unshared.text
    assert unshared.json()["revision"] == 3
    assert unshared.json()["payload"]["visibility"] == "private"
    assert unshared.json()["payload"]["share"] is None


def test_saved_exploration_share_openapi_requires_control_headers(client) -> None:
    schema = client.get("/openapi.json").json()
    for suffix in ("share", "unshare"):
        operation = schema["paths"][
            f"/v1/ontology/explorations/{{exp_id}}/{suffix}"
        ]["post"]
        parameters = {
            (item["name"], item["in"]): item.get("required", False)
            for item in operation["parameters"]
        }
        assert parameters[("If-Match", "header")] is True
        assert parameters[("Idempotency-Key", "header")] is True
