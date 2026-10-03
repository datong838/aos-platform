"""E17-s3o-r: retain the original ToolBinding issuance receipt gap as RED."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aos_api.aip_assignee_resolution import UpsertToolBindingRequest
from aos_api.aip_assignee_resolution_store import AipAssigneeResolutionStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


@pytest.mark.xfail(strict=True, reason="original ToolBinding issuer has no persisted issuance receipt")
def test_original_tool_binding_write_has_same_transaction_issuance_receipt():
    scope = TenantScope("org-org", "dev-project")
    binding_id = f"s3or-{uuid4().hex}"
    AipAssigneeResolutionStore().upsert_tool_binding(
        scope,
        UpsertToolBindingRequest(
            binding_id=binding_id, tool_id="test-only-tool", version=1,
            agent_instance_id="test-only-agent",
        ),
        now=datetime.now(UTC),
    )
    with connect(scope) as conn:
        binding = conn.execute("""SELECT binding_id,version FROM aip_tool_binding
            WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
            (*scope.key, binding_id)).fetchone()
        receipts = conn.execute("""SELECT count(*) AS n
            FROM aip_agent_registry_receipt
            WHERE org_id=%s AND project_id=%s
              AND operation='tool_binding.upsert'
              AND result_ref->>'resourceId'=%s""",
            (*scope.key, binding_id)).fetchone()["n"]
    assert binding == {"binding_id": binding_id, "version": 1}
    assert receipts == 1
