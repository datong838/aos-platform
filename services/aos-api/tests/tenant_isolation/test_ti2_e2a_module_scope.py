from __future__ import annotations

import uuid

import pytest

from aos_api.canvas_config import get_config, put_config
from aos_api.module_variables import (
    create_variable,
    delete_variable,
    get_variable,
    update_variable,
)
from aos_api.module_interfaces import get_interface, put_interface
from aos_api.module_events import create_event, delete_event, get_event, update_event
from aos_api.module_queries import create_query, delete_query, get_query
from aos_api.tenant_scope import TenantScope
from aos_api.widget_instances import (
    create_instance,
    delete_instance,
    get_instance,
    update_instance,
)


def _scopes() -> tuple[TenantScope, TenantScope]:
    suffix = uuid.uuid4().hex[:8]
    return (
        TenantScope(f"org-a-{suffix}", f"ws-a-{suffix}"),
        TenantScope(f"org-b-{suffix}", f"ws-b-{suffix}"),
    )


def test_canvas_fails_closed_on_same_legacy_id_across_tenants() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    created = put_config(scope_a, module_id, {"type": "page"}, {})

    assert created["moduleId"] == module_id
    assert get_config(scope_b, module_id) is None
    with pytest.raises(PermissionError):
        put_config(scope_b, module_id, {"type": "other"}, {})
    assert get_config(scope_a, module_id)["layout"] == {"type": "page"}


def test_widget_get_update_delete_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    item = create_instance(scope_a, module_id, {"title": "A"})

    assert get_instance(scope_b, module_id, item["id"]) is None
    assert get_instance(scope_a, "other-module", item["id"]) is None
    assert update_instance(scope_b, module_id, item["id"], {"title": "B"}) is None
    assert delete_instance(scope_b, module_id, item["id"]) is False
    assert get_instance(scope_a, module_id, item["id"])["title"] == "A"


def test_variable_get_update_delete_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    item = create_variable(scope_a, module_id, {"name": "selected"})

    assert get_variable(scope_b, module_id, item["id"]) is None
    assert get_variable(scope_a, "other-module", item["id"]) is None
    assert update_variable(scope_b, module_id, item["id"], {"name": "leak"}) is None
    assert delete_variable(scope_b, module_id, item["id"]) is False
    assert get_variable(scope_a, module_id, item["id"])["name"] == "selected"


def test_query_get_delete_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    item = create_query(scope_a, module_id, {"name": "orders"})

    assert get_query(scope_b, module_id, item["id"]) is None
    assert get_query(scope_a, "other-module", item["id"]) is None
    assert delete_query(scope_b, module_id, item["id"]) is False
    assert get_query(scope_a, module_id, item["id"])["name"] == "orders"


def test_interface_fails_closed_on_same_legacy_id_across_tenants() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    put_interface(scope_a, module_id, {"name": "A"})

    assert get_interface(scope_b, module_id) is None
    with pytest.raises(PermissionError):
        put_interface(scope_b, module_id, {"name": "B"})
    assert get_interface(scope_a, module_id)["name"] == "A"


def test_event_get_update_delete_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    item = create_event(
        scope_a,
        module_id,
        {"name": "refresh", "trigger": {}, "action": {}},
    )

    assert get_event(scope_b, module_id, item["id"]) is None
    assert get_event(scope_a, "other-module", item["id"]) is None
    assert update_event(scope_b, module_id, item["id"], {"name": "leak"}) is None
    assert delete_event(scope_b, module_id, item["id"]) is False
    assert get_event(scope_a, module_id, item["id"])["name"] == "refresh"
