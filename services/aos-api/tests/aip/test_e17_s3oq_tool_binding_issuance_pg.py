"""E17-s3o-q: original ToolBinding write must keep exact-version history."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aos_api.aip_assignee_resolution import UpsertToolBindingRequest
from aos_api.aip_assignee_resolution_store import (
    AipAssigneeResolutionBlocked, AipAssigneeResolutionStore,
)
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.routers.aip_assignee_authority import upsert_tool_binding
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 10, 3, 2, 0, tzinfo=UTC)


def _request(binding_id: str, *, version: int = 1,
             tool_id: str = "tool.query") -> UpsertToolBindingRequest:
    return UpsertToolBindingRequest(
        binding_id=binding_id, tool_id=tool_id, version=version,
        agent_instance_id="s3oq-test-only-agent",
    )


def _stored(binding_id: str):
    with connect(SCOPE) as conn:
        return conn.execute("""SELECT tool_id,version FROM aip_tool_binding
            WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
            (*SCOPE.key, binding_id)).fetchone()


def test_same_version_different_payload_cannot_rewrite_binding():
    binding_id = f"s3oq-{uuid4().hex}"
    store = AipAssigneeResolutionStore()
    store.upsert_tool_binding(SCOPE, _request(binding_id), now=NOW)
    with pytest.raises(AipAssigneeResolutionBlocked):
        store.upsert_tool_binding(
            SCOPE, _request(binding_id, tool_id="tool.other"), now=NOW)
    assert _stored(binding_id) == {"tool_id": "tool.query", "version": 1}


def test_lower_version_cannot_replace_newer_binding():
    binding_id = f"s3oq-{uuid4().hex}"
    store = AipAssigneeResolutionStore()
    store.upsert_tool_binding(SCOPE, _request(binding_id, version=2), now=NOW)
    with pytest.raises(AipAssigneeResolutionBlocked):
        store.upsert_tool_binding(SCOPE, _request(binding_id), now=NOW)
    assert _stored(binding_id) == {"tool_id": "tool.query", "version": 2}


def test_exact_replay_and_next_version_remain_usable():
    binding_id = f"s3oq-{uuid4().hex}"
    store = AipAssigneeResolutionStore()
    first = store.upsert_tool_binding(SCOPE, _request(binding_id), now=NOW)
    replay = store.upsert_tool_binding(SCOPE, _request(binding_id), now=NOW)
    next_version = store.upsert_tool_binding(
        SCOPE, _request(binding_id, version=2, tool_id="tool.other"), now=NOW)
    assert replay == first
    assert next_version.version == 2
    assert _stored(binding_id) == {"tool_id": "tool.other", "version": 2}


def test_http_command_maps_version_conflict_without_changing_binding():
    binding_id = f"s3oq-{uuid4().hex}"
    store = AipAssigneeResolutionStore()
    principal = Principal(subject="test-only", org_id="org-org",
                          project_id="dev-project", roles=["admin"], token_kind="oidc")
    upsert_tool_binding(_request(binding_id), principal=principal, store=store)
    with pytest.raises(ApiError) as error:
        upsert_tool_binding(_request(binding_id, tool_id="tool.other"),
                            principal=principal, store=store)
    assert error.value.status_code == 409
    assert error.value.code == "TOOL_BINDING_VERSION_CONFLICT"
    assert _stored(binding_id) == {"tool_id": "tool.query", "version": 1}
