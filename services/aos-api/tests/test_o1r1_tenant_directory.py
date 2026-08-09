from __future__ import annotations

import pytest

from aos_api.errors import ApiError
from aos_api.tenant_directory_service import require_workspace
from aos_api.tenant_scope import TenantScope


def test_registered_workspace_is_accepted() -> None:
    require_workspace(TenantScope("dev-org", "dev-project"))


def test_unknown_workspace_is_rejected_fail_closed() -> None:
    with pytest.raises(ApiError) as caught:
        require_workspace(TenantScope("dev-org", "unknown-workspace"))
    assert caught.value.status_code == 403
    assert caught.value.code == "AUTH_TENANT_UNKNOWN"
