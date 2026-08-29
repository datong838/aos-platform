"""Governed Workshop AIP FeatureActivation command acceptance."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.auth import Principal
from aos_api.ecommerce_workshop_contracts import WorkshopFeatureActivationCommandRequest
from aos_api.ecommerce_workshop_feature_activation import (
    EcommerceWorkshopFeatureActivationService,
    WorkshopFeatureActivationForbidden,
)

HASH = "sha256:" + "a" * 64


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._row


class _Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((statement, params))
        return _Result(self.row)


def _principal(*roles: str) -> Principal:
    return Principal(
        subject="operator-1",
        org_id="org-org",
        project_id="dev-project",
        roles=list(roles),
    )


def _service(row):
    conn = _Connection(row)

    @contextmanager
    def factory(scope):
        assert scope.key == ("org-org", "dev-project")
        yield conn

    return EcommerceWorkshopFeatureActivationService(factory), conn


def _row(*, replayed=False, operation="activate", status="active"):
    return {
        "receipt_data": {
            "schemaVersion": "aos.ecommerce-workshop.feature-activation-command-receipt/v1",
            "receiptId": "wcat-123",
            "featureId": "aip.analysis",
            "operation": operation,
            "revision": 1,
            "status": status,
            "contentHash": HASH,
            "createdAt": datetime(2026, 8, 29, 9, tzinfo=UTC),
        },
        "replayed": replayed,
    }


def test_activate_is_tenant_bound_hashed_and_returns_receipt() -> None:
    service, conn = _service(_row())
    expires = datetime.now(UTC) + timedelta(hours=1)
    response = service.execute(
        principal=_principal("admin"),
        feature_id="aip.analysis",
        operation="activate",
        body=WorkshopFeatureActivationCommandRequest(
            expectedRevision=0, contentHash=HASH, expiresAt=expires
        ),
        idempotency_key="activate-1",
    )
    assert response.tenant.org_id == "org-org"
    assert response.receipt.status == "active"
    assert response.replayed is False
    statement, params = conn.calls[0]
    assert "ecommerce_workshop_feature_activation_command_wcat_001" in statement
    assert params[:6] == (
        "aip.analysis",
        "activate",
        0,
        HASH,
        expires,
        "activate-1",
    )
    assert params[6].startswith("sha256:") and len(params[6]) == 71
    assert params[7] == "operator-1"


def test_non_admin_cannot_reach_database() -> None:
    service, conn = _service(_row())
    with pytest.raises(WorkshopFeatureActivationForbidden):
        service.execute(
            principal=_principal("developer"),
            feature_id="aip.analysis",
            operation="revoke",
            body=WorkshopFeatureActivationCommandRequest(expectedRevision=1),
            idempotency_key="revoke-1",
        )
    assert conn.calls == []


def test_activate_requires_exact_hash_and_future_expiry() -> None:
    service, conn = _service(_row())
    with pytest.raises(ValueError, match="contentHash and expiresAt"):
        service.execute(
            principal=_principal("workshop-admin"),
            feature_id="aip.analysis",
            operation="activate",
            body=WorkshopFeatureActivationCommandRequest(expectedRevision=0),
            idempotency_key="activate-1",
        )
    with pytest.raises(ValueError, match="future"):
        service.execute(
            principal=_principal("workshop-admin"),
            feature_id="aip.analysis",
            operation="activate",
            body=WorkshopFeatureActivationCommandRequest(
                expectedRevision=0,
                contentHash=HASH,
                expiresAt=datetime.now(UTC) - timedelta(seconds=1),
            ),
            idempotency_key="activate-2",
        )
    assert conn.calls == []


def test_revoke_rejects_activation_content_and_preserves_replay_flag() -> None:
    service, conn = _service(_row(replayed=True, operation="revoke", status="revoked"))
    with pytest.raises(ValueError, match="does not accept"):
        service.execute(
            principal=_principal("admin"),
            feature_id="aip.analysis",
            operation="revoke",
            body=WorkshopFeatureActivationCommandRequest(
                expectedRevision=1, contentHash=HASH
            ),
            idempotency_key="revoke-bad",
        )
    response = service.execute(
        principal=_principal("platform-admin"),
        feature_id="aip.analysis",
        operation="revoke",
        body=WorkshopFeatureActivationCommandRequest(expectedRevision=1),
        idempotency_key="revoke-1",
    )
    assert response.replayed is True
    assert response.receipt.status == "revoked"
    assert len(conn.calls) == 1


def test_list_current_is_tenant_bound_and_returns_latest_projection() -> None:
    activated_at = datetime(2026, 8, 29, 9, tzinfo=UTC)
    service, conn = _service(
        [
            {
                "feature_id": "aip.analysis",
                "revision": 2,
                "content_hash": HASH,
                "status": "active",
                "activated_at": activated_at,
                "expires_at": activated_at + timedelta(hours=2),
            }
        ]
    )
    response = service.list_current(principal=_principal("developer"))
    assert response.tenant.org_id == "org-org"
    assert response.items[0].feature_id == "aip.analysis"
    assert response.items[0].revision == 2
    statement, params = conn.calls[0]
    assert "DISTINCT ON(feature_id)" in statement
    assert params == ("org-org", "dev-project")
