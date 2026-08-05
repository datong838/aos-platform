from __future__ import annotations

import uuid

import pytest
from aos_api.canvas_config import get_config, put_config
from aos_api.db import connect
from aos_api.module_deployments import deploy, get_deployment, rollback
from aos_api.module_events import create_event, delete_event, get_event, update_event
from aos_api.module_interfaces import get_interface, put_interface
from aos_api.module_queries import create_query, delete_query, get_query
from aos_api.module_store import create_module
from aos_api.module_variables import (
    create_variable,
    delete_variable,
    get_variable,
    update_variable,
)
from aos_api.tenant_scope import TenantScope
from aos_api.themes import create_theme, delete_theme, get_theme, update_theme
from aos_api.widget_catalog import create_widget, get_widget, list_widgets
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


def _create_module(scope: TenantScope, module_id: str) -> None:
    created = create_module(scope, {"id": module_id, "name": module_id})
    assert created["id"] == module_id


def _ensure_meta_workspace(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO meta_workspace (org_id,project_id,name) VALUES (%s,%s,%s) "
            "ON CONFLICT (org_id,project_id) DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.commit()


def test_canvas_fails_closed_on_same_legacy_id_across_tenants() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    _create_module(scope_a, module_id)
    created = put_config(scope_a, module_id, {"type": "page"}, {})

    assert created["moduleId"] == module_id
    assert get_config(scope_b, module_id) is None
    with pytest.raises(PermissionError):
        put_config(scope_b, module_id, {"type": "other"}, {})
    assert get_config(scope_a, module_id)["layout"] == {"type": "page"}


def test_widget_get_update_delete_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    _create_module(scope_a, module_id)
    item = create_instance(scope_a, module_id, {"title": "A"})

    assert get_instance(scope_b, module_id, item["id"]) is None
    assert get_instance(scope_a, "other-module", item["id"]) is None
    assert update_instance(scope_b, module_id, item["id"], {"title": "B"}) is None
    assert delete_instance(scope_b, module_id, item["id"]) is False
    assert get_instance(scope_a, module_id, item["id"])["title"] == "A"


def test_variable_get_update_delete_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    _create_module(scope_a, module_id)
    item = create_variable(scope_a, module_id, {"name": "selected"})

    assert get_variable(scope_b, module_id, item["id"]) is None
    assert get_variable(scope_a, "other-module", item["id"]) is None
    assert update_variable(scope_b, module_id, item["id"], {"name": "leak"}) is None
    assert delete_variable(scope_b, module_id, item["id"]) is False
    assert get_variable(scope_a, module_id, item["id"])["name"] == "selected"


def test_query_get_delete_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    _create_module(scope_a, module_id)
    item = create_query(scope_a, module_id, {"name": "orders"})

    assert get_query(scope_b, module_id, item["id"]) is None
    assert get_query(scope_a, "other-module", item["id"]) is None
    assert delete_query(scope_b, module_id, item["id"]) is False
    assert get_query(scope_a, module_id, item["id"])["name"] == "orders"


def test_interface_fails_closed_on_same_legacy_id_across_tenants() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    _create_module(scope_a, module_id)
    put_interface(scope_a, module_id, {"name": "A"})

    assert get_interface(scope_b, module_id) is None
    with pytest.raises(PermissionError):
        put_interface(scope_b, module_id, {"name": "B"})
    assert get_interface(scope_a, module_id)["name"] == "A"


def test_event_get_update_delete_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    _create_module(scope_a, module_id)
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


def test_deployment_and_rollback_are_tenant_and_module_scoped() -> None:
    scope_a, scope_b = _scopes()
    module_id = f"module-{uuid.uuid4().hex}"
    _create_module(scope_a, module_id)
    item = deploy(scope_a, module_id, "dev")

    assert get_deployment(scope_b, module_id, item["id"]) is None
    assert get_deployment(scope_a, "other-module", item["id"]) is None
    assert rollback(scope_b, module_id, item["id"]) is None
    assert rollback(scope_a, "other-module", item["id"]) is None
    assert rollback(scope_a, module_id, item["id"])["status"] == "rollback"


def test_theme_crud_allows_same_logical_id_in_two_tenants() -> None:
    scope_a, scope_b = _scopes()
    _ensure_meta_workspace(scope_a)
    _ensure_meta_workspace(scope_b)
    theme_id = f"theme-{uuid.uuid4().hex}"
    create_theme(scope_a, {"id": theme_id, "name": "A"})

    assert get_theme(scope_b, theme_id) is None
    assert update_theme(scope_b, theme_id, {"name": "leak"}) is None
    assert delete_theme(scope_b, theme_id) is False
    create_theme(scope_b, {"id": theme_id, "name": "B"})
    assert get_theme(scope_a, theme_id)["name"] == "A"
    assert get_theme(scope_b, theme_id)["name"] == "B"
    assert delete_theme(scope_a, theme_id) is True
    assert delete_theme(scope_b, theme_id) is True


def test_widget_catalog_allows_same_logical_id_in_two_tenants() -> None:
    scope_a, scope_b = _scopes()
    _ensure_meta_workspace(scope_a)
    _ensure_meta_workspace(scope_b)
    widget_id = f"widget-{uuid.uuid4().hex}"
    create_widget(scope_a, {"id": widget_id, "name": "A", "source": "custom"})

    assert get_widget(scope_b, widget_id) is None
    assert all(item["id"] != widget_id for item in list_widgets(scope_b))
    create_widget(scope_b, {"id": widget_id, "name": "B"})
    assert get_widget(scope_a, widget_id)["name"] == "A"
    assert get_widget(scope_b, widget_id)["name"] == "B"
    with connect(scope_a) as conn:
        conn.execute("DELETE FROM widget_catalog WHERE id=%s", (widget_id,))
        conn.commit()
    with connect(scope_b) as conn:
        conn.execute("DELETE FROM widget_catalog WHERE id=%s", (widget_id,))
        conn.commit()
