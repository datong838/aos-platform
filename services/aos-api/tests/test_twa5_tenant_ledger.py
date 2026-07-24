"""TWA.5 — tenant ledger P0 clear + module tenant filter helpers (no PG)."""
from __future__ import annotations

from aos_api.tenant_scope import (
    belongs_to_tenant,
    filter_by_tenant,
    load_tenant_ledger,
    p0_open_gaps,
)


def test_p0_ledger_has_no_gaps():
    ledger = load_tenant_ledger()
    assert ledger["task"] == "TWA.5"
    gaps = p0_open_gaps(ledger)
    assert gaps == [], f"P0 GAP remaining: {gaps}"
    p0 = [e for e in ledger["entries"] if e["priority"] == "P0"]
    assert any(e["id"] == "L05" and e["status"] == "OK" for e in p0)


def test_filter_by_tenant_isolates_projects():
    items = [
        {"id": "a", "orgId": "org-a", "projectId": "prj-1"},
        {"id": "b", "orgId": "org-a", "projectId": "prj-2"},
        {"id": "c", "orgId": "org-b", "projectId": "prj-1"},
    ]
    got = filter_by_tenant(items, "org-a", "prj-1")
    assert [x["id"] for x in got] == ["a"]


def test_belongs_to_tenant():
    mod = {"id": "m1", "orgId": "org-a", "projectId": "prj-1"}
    assert belongs_to_tenant(mod, "org-a", "prj-1")
    assert not belongs_to_tenant(mod, "org-a", "prj-2")
    assert not belongs_to_tenant(None, "org-a", "prj-1")


def test_module_store_signatures_require_tenant(monkeypatch):
    """Call contract: list/get require org+project (signature smoke, no DB)."""
    import inspect

    from aos_api import module_store

    sig = inspect.signature(module_store.list_modules)
    assert "org_id" in sig.parameters
    assert "project_id" in sig.parameters
    sig_g = inspect.signature(module_store.get_module)
    assert list(sig_g.parameters)[:3] == ["module_id", "org_id", "project_id"]
