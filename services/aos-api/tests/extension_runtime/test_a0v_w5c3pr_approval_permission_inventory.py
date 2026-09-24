import pytest

import a0v_w5c3pr_approval_permission_inventory as wave
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize("scope", [
    TenantScope("dev-org", "dev-project"),
    TenantScope("org-org", "other-project"),
])
def test_head_action_connection_rejects_other_tenant_without_connecting(monkeypatch, scope):
    monkeypatch.setattr(wave, "database_connect", lambda _: (_ for _ in ()).throw(
        AssertionError("must not connect")))
    with pytest.raises(ValueError, match="EXACT_TENANT_REQUIRED"):
        with wave.head_action_connection(scope):
            pass
