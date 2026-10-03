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
    agent_id = f"s3or-agent-{uuid4().hex}"
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_agent_template_revision(
                 template_id,revision,display_name,role_key,lifecycle,source_ref,
                 source_license,manifest,content_hash,created_by)
               VALUES('template-s3or',1,'S3OR','tester','published','{}',
                      'internal','{}',%s,'tester') ON CONFLICT DO NOTHING""",
            ("f" * 64,),
        )
        conn.execute(
            """INSERT INTO aip_agent_instance(
                 org_id,project_id,instance_id,template_id,template_revision,status,
                 overlay,version,created_by)
               VALUES(%s,%s,%s,'template-s3or',1,'active','{}',1,'tester')""",
            (*scope.key, agent_id),
        )
        conn.commit()
    AipAssigneeResolutionStore().upsert_tool_binding(
        scope,
        UpsertToolBindingRequest(
            binding_id=binding_id, tool_id="test-only-tool", version=1,
            agent_instance_id=agent_id,
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
