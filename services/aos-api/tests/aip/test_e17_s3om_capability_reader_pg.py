"""E17-s3o-m: audit the real readiness DB login before CapabilityBinding UPDATE."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import (
    EvaluateOperationalBindingRequest, OperationalBindingDependencies,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryPersistenceError
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.db import connect, connect as original_db_connect

from tests.aip.test_e17_s3ol_capability_issuer_pg import capability_case, capability_issuer


@pytest.mark.xfail(
    strict=True,
    reason="Capability readiness still falls back to the preview owner login",
)
def test_original_evaluate_reader_does_not_fall_back_to_preview_owner(
    capability_case, capability_issuer, monkeypatch,
):
    scope, request = capability_case
    observed: list[tuple[str, str]] = []

    @contextmanager
    def traced_db_connect(*args, **kwargs):
        with original_db_connect(*args, **kwargs) as conn:
            row = conn.execute("SELECT session_user AS login,current_user AS role").fetchone()
            observed.append((row["login"], row["role"]))
            yield conn

    monkeypatch.setattr("aos_api.aip_binding_readiness_service.db_connect", traced_db_connect)
    service = AipCapabilityBindingService(connect_factory=capability_issuer)
    created, _ = service.create(
        scope, request, idempotency_key=f"s3om:create:{request.binding_id}",
        actor="test-only", occurred_at=datetime.now(UTC))
    try:
        service.evaluate(
            scope, created.binding_id,
            EvaluateOperationalBindingRequest(
                expected_version=1, dependencies=OperationalBindingDependencies()),
            idempotency_key=f"s3om:evaluate:{created.binding_id}",
            actor="test-only", evaluated_at=datetime.now(UTC))
    except AipAgentRegistryPersistenceError:
        # The create-only issuer also lacks UPDATE; that is a separate ACL gate.
        pass
    with connect(scope) as conn:
        assert conn.execute("SELECT version FROM aip_capability_binding WHERE binding_id=%s",
                            (created.binding_id,)).fetchone()["version"] == 1
        assert conn.execute("SELECT 1 FROM aip_agent_registry_receipt "
                            "WHERE operation='capability_binding.evaluate' AND result_ref->>'resourceId'=%s",
                            (created.binding_id,)).fetchone() is None
    assert observed and all(login == "aos_aip_capability_issuer" and role == login
                            for login, role in observed), observed
