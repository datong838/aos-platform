from uuid import uuid4

import pytest

from aos_api.ecommerce_dispatch_configuration_owner import EcommerceDispatchConfigurationOwner
from aos_api.tenant_scope import TenantScope
from tests.test_ecommerce_dispatch_configuration_receipt import row


class _Result:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        return self._value


class _Connection:
    def __init__(self, scope):
        self.scope = scope
        self.receipt_id = uuid4()
        self.function_calls = 0

    def execute(self, query, params=()):
        if query.startswith("SELECT current_user"):
            return _Result(
                {
                    "role": "aos_extension_maintainer",
                    "org_id": self.scope.org_id,
                    "project_id": self.scope.project_id,
                }
            )
        if "extension_dispatch_configuration_refresh_a0v_068" in query:
            self.function_calls += 1
            return _Result({"receipt_id": self.receipt_id})
        if "extension_dispatch_configuration_refresh_receipt" in query:
            return _Result({"receipt_id": self.receipt_id})
        raise AssertionError(query)


def test_owner_checks_current_approval_before_and_after_single_mutation(monkeypatch):
    scope = TenantScope("org-org", "dev-project")
    command = row()["request"]
    owner = EcommerceDispatchConfigurationOwner()
    checks = []

    class Approval:
        def _approval_authority(self, conn, actual_scope, request, **kwargs):
            checks.append((actual_scope, request, kwargs))

    owner._approval = Approval()
    monkeypatch.setattr(
        "aos_api.ecommerce_dispatch_configuration_owner.decode_receipt",
        lambda value: {"receiptId": str(value["receipt_id"])},
    )
    conn = _Connection(scope)
    result = owner.execute(conn, scope=scope, command=command, actor="configuration-owner")

    assert result == {"receiptId": str(conn.receipt_id)}
    assert conn.function_calls == 1
    assert len(checks) == 2
    assert all(item[0] == scope for item in checks)
    assert all(item[2]["action_type_id"] == "ecommerce_dispatch_configuration_refresh" for item in checks)
    assert checks[0][2]["expected_payload"] == checks[1][2]["expected_payload"]


def test_owner_stops_when_post_mutation_approval_recheck_fails(monkeypatch):
    scope = TenantScope("org-org", "dev-project")
    owner = EcommerceDispatchConfigurationOwner()
    calls = 0

    class Approval:
        def _approval_authority(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PermissionError("approval expired")

    owner._approval = Approval()
    monkeypatch.setattr(
        "aos_api.ecommerce_dispatch_configuration_owner.decode_receipt",
        lambda value: value,
    )
    conn = _Connection(scope)
    with pytest.raises(PermissionError, match="approval expired"):
        owner.execute(
            conn,
            scope=scope,
            command=row()["request"],
            actor="configuration-owner",
        )
    assert conn.function_calls == 1
    assert calls == 2
