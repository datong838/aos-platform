"""Original active ToolBinding must fail before a write without formal source."""

from datetime import UTC, datetime

import pytest

from aos_api.aip_assignee_resolution import UpsertToolBindingRequest
from aos_api.aip_assignee_resolution_store import (
    AipAssigneeResolutionBlocked, AipAssigneeResolutionStore,
)
from aos_api.tenant_scope import TenantScope


@pytest.mark.xfail(strict=True, reason="formal signed ToolDefinition/issuer source contract absent")
def test_active_tool_binding_without_formal_source_never_opens_writer():
    def forbidden_writer(_scope):
        raise AssertionError("original owner writer opened without formal ToolDefinition")

    store = AipAssigneeResolutionStore(connect_factory=forbidden_writer)
    request = UpsertToolBindingRequest(
        binding_id="s3owaob6-test-only", tool_id="tool.no-current-signed-source",
        version=1, agent_instance_id="agent-test-only",
    )
    with pytest.raises(AipAssigneeResolutionBlocked, match="TOOL_BINDING_FORMAL_SOURCE_REQUIRED"):
        store.upsert_tool_binding(
            TenantScope("org-org", "dev-project"), request,
            now=datetime(2026, 10, 4, tzinfo=UTC),
        )
