"""Assignee write endpoints must reject non-formal actors before Store access."""

from __future__ import annotations

import pytest

from aos_api.aip_assignee_resolution import ResolveAssigneeRequest, UpsertToolBindingRequest
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef
from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers.aip_assignee_authority import resolve_assignee, upsert_tool_binding


class SpyStore:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def upsert_tool_binding(self, scope, body, *, now):
        self.calls.append(("tool", scope, body, now))
        return "tool-written"

    def resolve(self, scope, body, actor, *, now):
        self.calls.append(("resolution", scope, body, actor, now))
        return "resolution-written"


TOOL = UpsertToolBindingRequest(
    binding_id="test-only-binding", tool_id="test-only-tool", version=1,
    agent_instance_id="test-only-agent",
)
RESOLUTION = ResolveAssigneeRequest(
    subject_id="test-only-subject",
    assignee=AssigneeRef(kind=AssigneeKind.TOOL_BINDING,
                         resource_id="test-only-binding", version=1),
)


@pytest.mark.parametrize("command,body", [
    (upsert_tool_binding, TOOL), (resolve_assignee, RESOLUTION),
])
@pytest.mark.parametrize("token_kind,subject", [
    ("dev", "test-only-actor"), ("oidc", " "),
])
def test_untrusted_actor_cannot_enter_assignee_write(command, body, token_kind, subject):
    store = SpyStore()
    principal = Principal(subject=subject, org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind=token_kind)
    with pytest.raises(ApiError) as error:
        command(body, principal=principal, store=store)
    assert error.value.status_code == 403
    assert store.calls == []


@pytest.mark.parametrize("command,body,expected", [
    (upsert_tool_binding, TOOL, "tool-written"),
    (resolve_assignee, RESOLUTION, "resolution-written"),
])
def test_formal_actor_reaches_existing_role_and_tenant_path(command, body, expected):
    store = SpyStore()
    principal = Principal(subject="test-only-oidc-actor", org_id="org-org",
                          project_id="dev-project", roles=["admin"], token_kind="oidc")
    assert command(body, principal=principal, store=store) == expected
    assert len(store.calls) == 1
    assert store.calls[0][1].key == ("org-org", "dev-project")
