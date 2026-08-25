"""W-L20 AssigneeResolutionReceipt + ToolBinding fail-closed + publisher 1.3.0."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aos_api.aip_assignee_resolution import (
    AssigneeResolutionStatus,
    ResolveAssigneeRequest,
    UpsertToolBindingRequest,
)
from aos_api.aip_assignee_resolution_store import (
    AipAssigneeResolutionStore,
    assert_publisher_bundle_version_locked,
)
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef
from aos_api.aip_solution_pack_publisher import SOLUTION_PACK_VERSION
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 20, 7, 0, tzinfo=UTC)


def _active_agent(instance_id: str) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO aip_agent_template_revision(
                 template_id,revision,display_name,role_key,lifecycle,source_ref,
                 source_license,manifest,content_hash,created_by)
               VALUES('template-w-l20',1,'W-L20','tester','published','{}',
                      'internal','{}',%s,'tester') ON CONFLICT DO NOTHING""",
            ("d" * 64,),
        )
        conn.execute(
            """INSERT INTO aip_agent_instance(
                 org_id,project_id,instance_id,template_id,template_revision,status,
                 overlay,version,created_by)
               VALUES(%s,%s,%s,'template-w-l20',1,'active','{}',1,'tester')""",
            (*SCOPE.key, instance_id),
        )
        conn.commit()


def test_publisher_bundle_version_locked_at_1_3_0() -> None:
    assert SOLUTION_PACK_VERSION == "1.3.0"
    assert assert_publisher_bundle_version_locked() == "1.3.0"


def test_tool_binding_missing_blocks_and_exact_binding_resolves() -> None:
    store = AipAssigneeResolutionStore()
    binding_id = f"tb-{uuid4().hex[:10]}"
    missing = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"subj-{uuid4().hex[:8]}",
            assignee=AssigneeRef(
                kind=AssigneeKind.TOOL_BINDING,
                resource_id=binding_id,
                version=1,
            ),
        ),
        "tester",
        now=NOW,
    )
    assert missing.status is AssigneeResolutionStatus.BLOCKED
    assert "TOOL_BINDING_MISSING" in missing.blocker_codes

    instance_id = f"agent-{uuid4().hex[:8]}"
    _active_agent(instance_id)
    store.upsert_tool_binding(
        SCOPE,
        UpsertToolBindingRequest(
            binding_id=binding_id,
            tool_id="tool.query",
            version=1,
            agent_instance_id=instance_id,
        ),
        now=NOW,
    )
    resolved = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"subj-{uuid4().hex[:8]}",
            assignee=AssigneeRef(
                kind=AssigneeKind.TOOL_BINDING,
                resource_id=binding_id,
                version=1,
            ),
        ),
        "tester",
        now=NOW,
    )
    assert resolved.status is AssigneeResolutionStatus.RESOLVED
    assert resolved.resolved_ref
    assert "tool_binding:" in resolved.resolved_ref


def test_human_principal_requires_tenant_membership_not_global_catalog() -> None:
    store = AipAssigneeResolutionStore(
        membership_resolver=lambda org_id, project_id, subject: (
            org_id,
            project_id,
            subject,
        )
        == ("org-org", "dev-project", "user:owner")
    )
    receipt = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"subj-{uuid4().hex[:8]}",
            assignee=AssigneeRef(
                kind=AssigneeKind.HUMAN_PRINCIPAL,
                resource_id="user:owner",
                version=1,
            ),
        ),
        "tester",
        now=NOW,
    )
    assert receipt.status is AssigneeResolutionStatus.RESOLVED
    assert receipt.kind is AssigneeKind.HUMAN_PRINCIPAL
