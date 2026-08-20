"""Unit tests for W-T4 capability tool exits."""

from __future__ import annotations

from aos_api.aip_capability_tool_exits import (
    CAPABILITY_NAME_ZH,
    invoke_capability_tool,
    list_capability_tool_exits,
)
from aos_api.aip_solution_pack_publisher import CAPABILITY_IDS
from aos_api.tenant_scope import TenantScope


def test_lists_exactly_ten_capability_cards():
    scope = TenantScope("org-org", "dev-project")
    items = list_capability_tool_exits(scope, bindings=[])
    assert len(items) == 10
    assert [i["capabilityId"] for i in items] == list(CAPABILITY_IDS)
    assert all(i["blocked"] for i in items)
    assert all(i["blockedReason"] for i in items)


def test_healthy_binding_still_blocked_until_proxy():
    scope = TenantScope("org-org", "dev-project")
    bindings = [
        {
            "bindingId": "b1",
            "capability": {"assetId": "copy.generate"},
            "status": "active",
            "health": "healthy",
        }
    ]
    items = list_capability_tool_exits(scope, bindings=bindings)
    copy = next(i for i in items if i["capabilityId"] == "copy.generate")
    assert copy["blocked"] is True
    assert "代调门" in copy["blockedReason"]


def test_invoke_never_fakes_ok():
    result = invoke_capability_tool(
        "cap.copy.generate",
        binding={
            "capability": {"assetId": "copy.generate"},
            "status": "active",
            "health": "healthy",
        },
    )
    assert result["ok"] is False
    assert result["blocked"] is True
    assert CAPABILITY_NAME_ZH["copy.generate"]
