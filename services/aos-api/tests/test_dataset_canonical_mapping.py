from __future__ import annotations

import copy
from unittest.mock import patch

import pytest

from aos_api.auth import Principal
from aos_api.routers import analytics, wave_ext
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    canonical_qyh_source_for_pipeline,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
PRINCIPAL = Principal(subject="dataset-canonical-test", org_id=SCOPE.org_id, project_id=SCOPE.project_id)


@pytest.fixture(autouse=True)
def _restore_dataset_state() -> None:
    snapshot = copy.deepcopy(wave_ext._datasets)
    loaded = set(wave_ext._data_os_loaded_scopes)
    wave_ext._datasets.clear()
    wave_ext._data_os_loaded_scopes.add(SCOPE.key)
    yield
    wave_ext._datasets.clear()
    wave_ext._datasets.update(snapshot)
    wave_ext._data_os_loaded_scopes.clear()
    wave_ext._data_os_loaded_scopes.update(loaded)


def test_canonical_mapping_covers_twelve_unique_pipelines_and_object_types() -> None:
    assert len(CANONICAL_QYH_SOURCES) == 12
    assert len({item.pipeline_id for item in CANONICAL_QYH_SOURCES}) == 12
    assert len({item.object_type for item in CANONICAL_QYH_SOURCES}) == 12
    assert canonical_qyh_source_for_pipeline("P05-order-qyh").object_type == "Order"
    assert canonical_qyh_source_for_pipeline("P11-product-review-qyh").object_type == "ProductReview"
    assert canonical_qyh_source_for_pipeline("missing") is None


def test_dataset_list_projects_canonical_hint_without_mutating_stale_metadata() -> None:
    rid = "ri.aos.main.dataset.P05-order-qyh"
    key = wave_ext._resource_key(SCOPE, rid)
    wave_ext._datasets[key] = {
        "rid": rid,
        "pipelineId": "P05-order-qyh",
        "objectTypeHint": "P05-order-qyh",
        "name": "栖月汇-订单",
        "orgId": SCOPE.org_id,
        "projectId": SCOPE.project_id,
    }

    with patch.object(wave_ext, "_hydrate_data_os_scope", return_value=None):
        items = wave_ext.list_datasets(PRINCIPAL)["items"]

    by_pipeline = {item["pipelineId"]: item for item in items}
    assert len({item.pipeline_id for item in CANONICAL_QYH_SOURCES} - set(by_pipeline)) == 0
    assert by_pipeline["P05-order-qyh"]["objectTypeHint"] == "Order"
    assert by_pipeline["P11-product-review-qyh"]["objectTypeHint"] == "ProductReview"
    assert wave_ext._datasets[key]["objectTypeHint"] == "P05-order-qyh"


def test_analytics_lookup_supports_p09_to_p12_and_overrides_stale_hint_read_only() -> None:
    rid = "ri.aos.main.dataset.P11-product-review-qyh"
    key = wave_ext._resource_key(SCOPE, rid)
    wave_ext._datasets[key] = {
        "rid": rid,
        "pipelineId": "P11-product-review-qyh",
        "objectTypeHint": "P11-product-review-qyh",
        "name": "栖月汇-商品评价",
    }

    projected = analytics._lookup_dataset(PRINCIPAL, rid)
    assert projected is not None
    assert projected["objectTypeHint"] == "ProductReview"
    assert wave_ext._datasets[key]["objectTypeHint"] == "P11-product-review-qyh"

    wave_ext._datasets.clear()
    for source in CANONICAL_QYH_SOURCES[8:]:
        missing_rid = f"ri.aos.main.dataset.{source.pipeline_id}"
        fallback = analytics._lookup_dataset(PRINCIPAL, missing_rid)
        assert fallback is not None
        assert fallback["objectTypeHint"] == source.object_type
