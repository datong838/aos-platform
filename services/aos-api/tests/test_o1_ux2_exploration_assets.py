from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from aos_api.errors import ApiError
from aos_api.ontology_exploration_assets import (
    ObjectSetAssetPayload,
    append_asset,
    get_asset,
    list_assets,
    set_archived,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("dev-org", "dev-project")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _exploration(visibility: str = "private") -> dict[str, object]:
    return {
        "name": "高风险支付探索",
        "objectType": "Payment",
        "viewMode": "table",
        "visibility": visibility,
        "query": {"status": "pending"},
        "columns": [{"key": "pay_duration_min"}],
        "graph": {},
    }


def test_asset_cas_replay_visibility_archive_and_restore() -> None:
    asset_id = _id("exp")
    key = _id("idem")
    created, etag = append_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        payload=_exploration(),
        expected_revision=0,
        idempotency_key=key,
        actor="alice",
    )
    replay, replay_etag = append_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        payload=_exploration(),
        expected_revision=0,
        idempotency_key=key,
        actor="alice",
    )
    assert replay == created
    assert replay_etag == etag
    assert get_asset(SCOPE, kind="exploration", asset_id=asset_id, actor="bob") is None
    assert (
        get_asset(
            TenantScope("org-org", "dev-project"),
            kind="exploration",
            asset_id=asset_id,
            actor="alice",
        )
        is None
    )

    with pytest.raises(ApiError) as stale:
        append_asset(
            SCOPE,
            kind="exploration",
            asset_id=asset_id,
            payload={**_exploration(), "name": "stale"},
            expected_revision=0,
            idempotency_key=_id("stale"),
            actor="alice",
        )
    assert stale.value.status_code == 412

    updated, _ = append_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        payload={**_exploration("workspace"), "name": "共享支付探索"},
        expected_revision=1,
        idempotency_key=_id("update"),
        actor="alice",
    )
    assert updated["revision"] == 2
    assert get_asset(SCOPE, kind="exploration", asset_id=asset_id, actor="bob") is not None

    archived, archive_etag = set_archived(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        archived=True,
        expected_revision=2,
        idempotency_key=_id("archive"),
        actor="alice",
    )
    assert archived["archived"] is True
    assert get_asset(SCOPE, kind="exploration", asset_id=asset_id, actor="alice") is None
    restored, restore_etag = set_archived(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        archived=False,
        expected_revision=2,
        idempotency_key=_id("restore"),
        actor="alice",
    )
    assert restored["archived"] is False
    assert restore_etag == archive_etag


def test_object_set_is_single_type_and_items_are_persisted() -> None:
    with pytest.raises(ValidationError, match="OBJECT_SET_TYPE_MISMATCH"):
        ObjectSetAssetPayload.model_validate({
            "name": "mixed",
            "objectType": "Order",
            "items": [
                {"objectType": "Order", "objectId": "niushop:1:1"},
                {"objectType": "Payment", "objectId": "niushop:1:1"},
            ],
        })
    asset_id = _id("set")
    created, _ = append_asset(
        SCOPE,
        kind="object_set",
        asset_id=asset_id,
        payload={
            "name": "订单集",
            "objectType": "Order",
            "visibility": "private",
            "items": [
                {"objectType": "Order", "objectId": "niushop:1:1"},
                {"objectType": "Order", "objectId": "niushop:1:2"},
            ],
        },
        expected_revision=0,
        idempotency_key=_id("set"),
        actor="alice",
    )
    assert len(created["payload"]["items"]) == 2
    assert any(item["id"] == asset_id for item in list_assets(SCOPE, kind="object_set", actor="alice"))


def test_annotation_requires_typed_subject() -> None:
    with pytest.raises(ValidationError):
        append_asset(
            SCOPE,
            kind="annotation",
            asset_id=_id("ann"),
            payload={"title": "x", "body": "y", "subject": {"subjectType": "object_instance", "subjectId": "x"}},
            expected_revision=0,
            idempotency_key=_id("ann"),
            actor="alice",
        )


def test_http_exploration_requires_receipt_and_round_trips(client, auth_headers) -> None:
    body = _exploration()
    missing = client.post("/v1/ontology/explorations", json=body, headers=auth_headers)
    assert missing.status_code == 400
    headers = {**auth_headers, "Idempotency-Key": _id("http")}
    created = client.post("/v1/ontology/explorations", json=body, headers=headers)
    assert created.status_code == 200, created.text
    asset_id = created.json()["id"]
    etag = created.headers["etag"]
    reread = client.get(f"/v1/ontology/explorations/{asset_id}", headers=auth_headers)
    assert reread.status_code == 200
    assert reread.json() == created.json()
    assert reread.headers["etag"] == etag
    replay = client.post("/v1/ontology/explorations", json=body, headers=headers)
    assert replay.status_code == 200
    assert replay.json() == created.json()

    update_headers = {**auth_headers, "Idempotency-Key": _id("http-update"), "If-Match": etag}
    updated = client.put(
        f"/v1/ontology/explorations/{asset_id}",
        json={"name": "已更新"},
        headers=update_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == 2


def test_http_rejects_client_owner_and_scope(client, auth_headers) -> None:
    body = {**_exploration(), "owner": "mallory", "orgId": "org-org"}
    response = client.post(
        "/v1/ontology/explorations",
        json=body,
        headers={**auth_headers, "Idempotency-Key": _id("forged")},
    )
    assert response.status_code == 400
