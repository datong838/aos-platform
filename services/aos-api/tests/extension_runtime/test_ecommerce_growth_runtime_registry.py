from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from aos_api.ecommerce_growth_host_composition import (
    ECOMMERCE_GROWTH_OPERATIONS,
    build_registration_only_ecommerce_growth_registry,
    build_runtime_ecommerce_growth_registry,
    select_ecommerce_growth_registry,
)
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostBlocked
from aos_api.ecommerce_growth_runtime_adapters import RUNTIME_ADAPTER_TYPES


DISPATCH_SOURCE = Path(__file__).resolve().parents[2] / "aos_api" / "routers" / "ecommerce_growth_dispatch.py"
REQUIRED_HOST_SERVICES = (
    ("ecommerce_growth_investigation_describe", "InvestigationDescribeHostService"),
    ("ecommerce_growth_case_put", "CasePutHostService"),
    ("ecommerce_growth_schedule_put", "SchedulePutHostService"),
    ("ecommerce_growth_schedule_trigger", "ScheduleTriggerHostService"),
    ("ecommerce_growth_data_fulfill", "DataFulfillHostService"),
    ("ecommerce_growth_analysis_advance", "AnalysisAdvanceHostService"),
    ("ecommerce_growth_review_advance", "ReviewAdvanceHostService"),
    ("ecommerce_growth_content_generate", "ContentGenerateHostService"),
    ("ecommerce_growth_content_review", "ContentReviewHostService"),
)


class FakeHostService:
    executor_identity = "ecommerce-growth-runtime-test"

    def revalidate(self, **_kwargs):
        return None

    def execute(self, **_kwargs):
        return {
            "receiptRef": {
                "resourceType": "BusinessInvestigationCase",
                "resourceId": "case-qyh-001",
                "revision": 3,
                "contentHash": "sha256:" + "a" * 64,
            }
        }

    def verify_receipt(self, **kwargs):
        return kwargs["receipt"]


def test_runtime_registry_factory_has_no_injection_surface():
    assert inspect.signature(build_runtime_ecommerce_growth_registry).parameters == {}
    with pytest.raises(TypeError):
        build_runtime_ecommerce_growth_registry(services={})


def test_runtime_registry_fails_closed_while_host_services_are_incomplete():
    with pytest.raises(EcommerceGrowthHostBlocked, match="AR2_7D_RUNTIME_WIRING_REQUIRED"):
        build_runtime_ecommerce_growth_registry()


def test_production_selector_stays_registration_only_until_nine_services_exist():
    selected = select_ecommerce_growth_registry()
    baseline = build_registration_only_ecommerce_growth_registry()
    assert selected.operation_ids == ECOMMERCE_GROWTH_OPERATIONS
    assert type(selected) is type(baseline)
    with pytest.raises(EcommerceGrowthHostBlocked, match="AR2_7D_RUNTIME_WIRING_REQUIRED"):
        selected._binding("ecommerce_growth_case_put").execute(
            transaction=None,
            scope=None,
            dispatch_ref=None,
            command={},
            checked_at=None,
            occurred_at=None,
        )


def test_http_dispatch_selects_production_registry_without_hardcoding_registration_only():
    source = DISPATCH_SOURCE.read_text()
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "aos_api.ecommerce_growth_host_composition"
        for alias in node.names
    }
    assert "select_ecommerce_growth_registry" in imported
    assert "build_registration_only_ecommerce_growth_registry" not in imported
    assert "select_ecommerce_growth_registry()" in source


def test_runtime_registry_builds_exact_nine_when_host_services_exist(monkeypatch):
    import aos_api.ecommerce_growth_runtime_adapters as adapters

    for operation_id, class_name in REQUIRED_HOST_SERVICES:
        monkeypatch.setattr(adapters, class_name, FakeHostService, raising=False)
    registry = build_runtime_ecommerce_growth_registry()
    assert registry.operation_ids == ECOMMERCE_GROWTH_OPERATIONS
    assert tuple(adapter.SPEC.operation_id for adapter in RUNTIME_ADAPTER_TYPES) == ECOMMERCE_GROWTH_OPERATIONS
    assert tuple(item[0] for item in REQUIRED_HOST_SERVICES) == ECOMMERCE_GROWTH_OPERATIONS
    execute = registry._binding("ecommerce_growth_case_put").execute
    assert execute.__self__.__class__ is FakeHostService
