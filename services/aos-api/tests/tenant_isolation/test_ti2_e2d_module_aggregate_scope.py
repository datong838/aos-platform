from __future__ import annotations

import inspect
import uuid
from pathlib import Path

from aos_api import module_store
from aos_api.tenant_scope import TenantScope


def _scopes() -> tuple[TenantScope, TenantScope]:
    suffix = uuid.uuid4().hex[:8]
    return (
        TenantScope(f"org-a-{suffix}", f"ws-a-{suffix}"),
        TenantScope(f"org-b-{suffix}", f"ws-b-{suffix}"),
    )


def test_module_aggregate_business_methods_require_scope_first() -> None:
    names = (
        "seed_modules_if_empty",
        "list_modules",
        "get_module",
        "create_module",
        "update_module",
        "touch_module",
        "publish_module",
        "module_runtime",
    )
    for name in names:
        parameters = list(inspect.signature(getattr(module_store, name)).parameters)
        assert parameters[0] == "scope", name


def test_e2_runtime_stores_have_no_default_tenant_identifiers() -> None:
    root = Path(module_store.__file__).parent
    files = (
        "module_store.py",
        "canvas_config.py",
        "widget_instances.py",
        "module_variables.py",
        "module_queries.py",
        "module_events.py",
        "module_interfaces.py",
        "module_deployments.py",
        "themes.py",
        "widget_catalog.py",
    )
    for filename in files:
        source = (root / filename).read_text(encoding="utf-8")
        assert "_DEFAULT_ORG" not in source, filename
        assert "_DEFAULT_PROJECT" not in source, filename


def test_module_aggregate_read_write_and_runtime_are_tenant_scoped() -> None:
    scope_a, scope_b = _scopes()
    item = module_store.create_module(scope_a, {"name": "orders"})
    module_id = item["id"]

    assert module_store.get_module(scope_b, module_id) is None
    assert module_store.update_module(scope_b, module_id, {"name": "leak"}) is None
    assert module_store.touch_module(scope_b, module_id) is False
    assert module_store.publish_module(scope_b, module_id) is None
    assert module_store.module_runtime(scope_b, module_id) is None

    updated = module_store.update_module(scope_a, module_id, {"name": "orders-a"})
    assert updated is not None
    assert updated["name"] == "orders-a"
    runtime = module_store.module_runtime(scope_a, module_id)
    assert runtime is not None
    assert (runtime["orgId"], runtime["projectId"]) == scope_a.key


def test_test_org_seed_does_not_populate_another_organization() -> None:
    suffix = uuid.uuid4().hex[:8]
    test_scope = TenantScope("dev-org", "dev-project")
    empty_scope = TenantScope(f"org-empty-{suffix}", f"ws-empty-{suffix}")

    module_store.seed_modules_if_empty(test_scope)

    assert module_store.list_modules(test_scope)
    assert module_store.list_modules(empty_scope) == []
