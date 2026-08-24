"""W-L16 SavedExploration ShareGrant + legacy engine disabled."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aos_api.errors import ApiError
from aos_api.oe_enhancements import ExplorationEngine, get_exploration_engine
from aos_api.ontology_exploration_assets import append_asset
from aos_api.ontology_exploration_share import (
    CreateShareGrantRequest,
    RevokeShareGrantRequest,
    create_share_grant,
    resolve_share_grant,
    resolve_shared_exploration,
    revoke_share_grant,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "user:owner"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _create_private_exploration() -> tuple[str, int, str]:
    asset_id = _id("exp")
    created, etag = append_asset(
        SCOPE,
        kind="exploration",
        asset_id=asset_id,
        payload={
            "name": "W-L16 grant",
            "objectType": "Order",
            "viewMode": "table",
            "visibility": "private",
            "query": {},
            "columns": [],
            "graph": {},
            "sort": [],
        },
        expected_revision=0,
        idempotency_key=_id("create"),
        actor=ACTOR,
    )
    return asset_id, int(created["revision"]), etag


def test_legacy_in_memory_engine_is_disabled() -> None:
    with pytest.raises(RuntimeError, match="LEGACY_EXPLORATION_ENGINE_DISABLED"):
        ExplorationEngine()
    with pytest.raises(RuntimeError, match="LEGACY_EXPLORATION_ENGINE_DISABLED"):
        get_exploration_engine()


def test_share_grant_create_resolve_revoke_and_expiry() -> None:
    asset_id, revision, _etag = _create_private_exploration()
    expires = datetime.now(UTC) + timedelta(hours=1)
    grant = create_share_grant(
        SCOPE,
        asset_id=asset_id,
        actor=ACTOR,
        body=CreateShareGrantRequest(expiresAt=expires, granteeScope="link"),
        idempotency_key=_id("grant"),
        expected_revision=revision,
    )
    assert grant.status == "active"
    assert grant.opaque_ref
    resolved = resolve_share_grant(SCOPE, grant.opaque_ref)
    assert resolved.grant_id == grant.grant_id
    assert resolved.asset_revision == revision

    revoked = revoke_share_grant(
        SCOPE,
        opaque_ref=grant.opaque_ref,
        actor=ACTOR,
        body=RevokeShareGrantRequest(expectedVersion=grant.version, reason="done"),
        idempotency_key=_id("revoke"),
    )
    assert revoked.status == "revoked"
    with pytest.raises(ApiError) as exc:
        resolve_share_grant(SCOPE, grant.opaque_ref)
    assert exc.value.code == "SHARE_GRANT_REVOKED"


def test_share_grant_expiry_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import aos_api.ontology_exploration_share as share_mod

    asset_id, revision, _ = _create_private_exploration()
    expires = datetime.now(UTC) + timedelta(minutes=5)
    grant = create_share_grant(
        SCOPE,
        asset_id=asset_id,
        actor=ACTOR,
        body=CreateShareGrantRequest(expiresAt=expires),
        idempotency_key=_id("grant-exp"),
        expected_revision=revision,
    )
    monkeypatch.setattr(
        share_mod, "_now", lambda: expires + timedelta(seconds=1)
    )
    with pytest.raises(ApiError) as exc:
        resolve_share_grant(SCOPE, grant.opaque_ref)
    assert exc.value.code == "SHARE_GRANT_EXPIRED"


def test_share_grant_markings_fail_closed() -> None:
    asset_id, revision, _ = _create_private_exploration()
    grant = create_share_grant(
        SCOPE,
        asset_id=asset_id,
        actor=ACTOR,
        body=CreateShareGrantRequest(
            expiresAt=datetime.now(UTC) + timedelta(hours=1),
            markings=["restricted"],
        ),
        idempotency_key=_id("grant-marking"),
        expected_revision=revision,
        grantor_markings=["public", "restricted"],
    )
    with pytest.raises(ApiError) as exc:
        resolve_shared_exploration(SCOPE, grant.opaque_ref, authorized_markings=["public"])
    assert exc.value.code == "SHARE_GRANT_MARKING_FORBIDDEN"


def test_share_grant_http_create_resolve_revoke(client, auth_headers) -> None:
    created = client.post(
        "/v1/ontology/explorations",
        headers={**auth_headers, "Idempotency-Key": _id("http-create")},
        json={
            "name": "HTTP grant",
            "objectType": "Order",
            "viewMode": "table",
            "visibility": "private",
        },
    )
    assert created.status_code == 200, created.text
    asset_id = created.json()["id"]
    expires = datetime.now(UTC) + timedelta(hours=2)
    grant = client.post(
        f"/v1/ontology/explorations/{asset_id}/share-grants",
        headers={
            **auth_headers,
            "Idempotency-Key": _id("http-grant"),
            "If-Match": created.headers["etag"],
        },
        json={"expiresAt": expires.isoformat(), "granteeScope": "link"},
    )
    assert grant.status_code == 201, grant.text
    opaque = grant.json()["opaqueRef"]
    resolved = client.get(
        f"/v1/ontology/exploration-share-grants/{opaque}",
        headers=auth_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "active"
    shared = client.get(
        f"/v1/ontology/exploration-share-grants/{opaque}/exploration",
        headers=auth_headers,
    )
    assert shared.status_code == 200, shared.text
    assert shared.json()["grant"]["assetId"] == asset_id
    assert shared.json()["exploration"]["id"] == asset_id
    assert shared.json()["exploration"]["payload"]["visibility"] == "private"
    revoked = client.post(
        f"/v1/ontology/exploration-share-grants/{opaque}/revoke",
        headers={**auth_headers, "Idempotency-Key": _id("http-revoke")},
        json={"expectedVersion": grant.json()["version"], "reason": "cleanup"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    gone = client.get(
        f"/v1/ontology/exploration-share-grants/{opaque}",
        headers=auth_headers,
    )
    assert gone.status_code == 410
    shared_gone = client.get(
        f"/v1/ontology/exploration-share-grants/{opaque}/exploration",
        headers=auth_headers,
    )
    assert shared_gone.status_code == 410
