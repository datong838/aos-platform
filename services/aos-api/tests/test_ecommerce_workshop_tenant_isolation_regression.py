"""R2-06: ecommerce Workshop tenant isolation regression matrix."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from starlette.requests import Request

from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers import ecommerce_workshop


ORG_SCOPE = ("org-org", "dev-project")
CANARY_SCOPE = ("dev-org", "dev-project")


def _principal(org_id: str) -> Principal:
    return Principal(
        subject=f"user:{org_id}",
        org_id=org_id,
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )


def _request(query: bytes = b"") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": query,
            "headers": [],
            "client": ("test", 1),
            "server": ("test", 80),
        }
    )


class _Catalog:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_readiness(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return object()


class _View:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def read(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return object()


class _Cockpit:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def read_core(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return object()


PageCall = Callable[[Request, Principal, _Catalog, Any], object]


def _task_cockpit(
    request: Request, principal: Principal, catalog: _Catalog, service: _Cockpit
) -> object:
    return ecommerce_workshop.get_ecommerce_workshop_task_cockpit_core(
        request=request,
        principal=principal,
        catalog=catalog,  # type: ignore[arg-type]
        cockpit=service,  # type: ignore[arg-type]
        status=None,
        limit=50,
        cursor=None,
    )


def _view_call(function_name: str, dependency_name: str) -> PageCall:
    function = getattr(ecommerce_workshop, function_name)

    def call(
        request: Request, principal: Principal, catalog: _Catalog, service: _View
    ) -> object:
        return function(
            request=request,
            principal=principal,
            catalog=catalog,
            **{dependency_name: service},
        )

    return call


PAGE_CALLS: list[tuple[str, PageCall, type[_Cockpit] | type[_View]]] = [
    ("日常任务总控", _task_cockpit, _Cockpit),
    (
        "内容与活动工作台",
        _view_call(
            "get_ecommerce_workshop_content_campaign_view", "content_campaign"
        ),
        _View,
    ),
    (
        "统一运营驾驶舱",
        _view_call("get_ecommerce_workshop_operations_view", "operations"),
        _View,
    ),
    (
        "达人邀约驾驶舱",
        _view_call("get_ecommerce_workshop_creator_growth_view", "creator_growth"),
        _View,
    ),
    (
        "多媒体内容生产",
        _view_call("get_ecommerce_workshop_media_studio_view", "media_studio"),
        _View,
    ),
    (
        "经营参谋",
        _view_call("get_ecommerce_workshop_analyst_view", "analyst"),
        _View,
    ),
    (
        "价格治理驾驶舱",
        _view_call("get_ecommerce_workshop_price_governance_view", "price_governance"),
        _View,
    ),
    (
        "客户关系工作台",
        _view_call("get_ecommerce_workshop_customer_view", "customer"),
        _View,
    ),
]


@pytest.mark.parametrize(("page", "call", "service_type"), PAGE_CALLS)
@pytest.mark.parametrize("scope", [ORG_SCOPE, CANARY_SCOPE])
def test_all_eight_pages_derive_scope_only_from_principal(
    page: str,
    call: PageCall,
    service_type: type[_Cockpit] | type[_View],
    scope: tuple[str, str],
) -> None:
    del page
    principal = _principal(scope[0])
    catalog = _Catalog()
    service = service_type()

    result = call(_request(), principal, catalog, service)

    assert result is not None
    assert len(catalog.calls) == 1
    assert catalog.calls[0]["org_id"] == scope[0]
    assert catalog.calls[0]["project_id"] == scope[1]
    assert len(service.calls) == 1
    assert service.calls[0]["org_id"] == scope[0]
    assert service.calls[0]["project_id"] == scope[1]


@pytest.mark.parametrize(("page", "call", "service_type"), PAGE_CALLS)
def test_all_eight_pages_reject_tenant_query_injection_before_dependencies(
    page: str,
    call: PageCall,
    service_type: type[_Cockpit] | type[_View],
) -> None:
    del page
    catalog = _Catalog()
    service = service_type()

    with pytest.raises(ApiError) as caught:
        call(_request(b"orgId=dev-org&projectId=dev-project"), _principal("org-org"), catalog, service)

    assert caught.value.code == "VALIDATION"
    assert catalog.calls == []
    assert service.calls == []
