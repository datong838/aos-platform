from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from aos_api.aip_analyst_templates import (
    AnalystTemplateCatalog,
    AnalystTemplateCatalogInvalid,
)
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


REPO_ROOT = Path(__file__).resolve().parents[4]
DOCUMENT = (
    REPO_ROOT
    / "bundles/solutions/ecommerce-growth/content/logic/"
    "ecommerce-analyst-query-templates.json"
)


class FakeConnection:
    def __init__(self, published: set[str]) -> None:
        self.published = published

    def execute(self, _query, params):
        requested = set(params[0])
        return self

    def fetchall(self):
        return [{"id": item} for item in sorted(self.published)]


def connect_factory(published: set[str]):
    @contextmanager
    def connect(_scope):
        yield FakeConnection(published)

    return connect


def test_catalog_returns_exact_six_roles_and_tenant_readiness() -> None:
    document = json.loads(DOCUMENT.read_text(encoding="utf-8"))
    all_types = {
        item
        for template in document["templates"]
        for item in template["requiredObjectTypes"]
    }
    catalog = AnalystTemplateCatalog(
        connect_factory=connect_factory(all_types),
        assert_visible=lambda _conn, _scope, _type: None,
    )
    result = catalog.list(TenantScope("org-org", "dev-project"))
    assert result.tenant.org_id == "org-org"
    assert result.count == len(result.items) == 6
    assert {item.role_id for item in result.items} == {
        "ecommerce.data_advisor",
        "ecommerce.content_officer",
        "ecommerce.shopping_advisor",
        "ecommerce.customer_service",
        "ecommerce.private_domain_manager",
        "ecommerce.campaign_planner",
    }
    assert all(item.readiness == "ready" for item in result.items)
    assert len(result.content_hash) == 64


def test_catalog_reports_exact_missing_type_without_fallback() -> None:
    def assert_visible(_conn, _scope, object_type):
        if object_type == "Payment":
            raise ApiError(code="NOT_FOUND", message="not installed", status_code=404)

    document = json.loads(DOCUMENT.read_text(encoding="utf-8"))
    all_types = {
        item
        for template in document["templates"]
        for item in template["requiredObjectTypes"]
    }
    result = AnalystTemplateCatalog(
        connect_factory=connect_factory(all_types),
        assert_visible=assert_visible,
    ).list(TenantScope("org-org", "dev-project"))
    data_advisor = next(
        item for item in result.items if item.role_id == "ecommerce.data_advisor"
    )
    assert data_advisor.readiness == "blocked"
    assert [item.code for item in data_advisor.blockers] == [
        "OBJECT_TYPE_NOT_INSTALLED"
    ]
    assert data_advisor.blockers[0].dependency_ref.resource_id == "Payment"
    assert all(item.default_object_type != "Category" for item in result.items)


def test_catalog_echoes_negative_canary_scope_without_cross_tenant_state() -> None:
    result = AnalystTemplateCatalog(
        connect_factory=connect_factory(set()),
        assert_visible=lambda _conn, _scope, _type: None,
    ).list(TenantScope("dev-org", "dev-project"))
    assert result.tenant.org_id == "dev-org"
    assert all(item.readiness == "blocked" for item in result.items)


def test_catalog_rejects_role_crosswalk_drift(tmp_path: Path) -> None:
    document = json.loads(DOCUMENT.read_text(encoding="utf-8"))
    document["templates"][0]["requiredLogicIds"] = ["D01"]
    path = tmp_path / "templates.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(AnalystTemplateCatalogInvalid, match="Logic crosswalk"):
        AnalystTemplateCatalog(
            document_path=path,
            connect_factory=connect_factory(set()),
        ).list(TenantScope("org-org", "dev-project"))
