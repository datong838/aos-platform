"""W2-AX · Dataset Preview Health 组测试（ColumnStats / PreviewViews / DataHealthCheck）."""
from __future__ import annotations

import threading
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.routers.dataset_preview_health import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-dph",
}


# ════════════════════ ColumnStatsEngine ════════════════════

class TestColumnStats:
    def setup_method(self) -> None:
        from aos_api.dataset_preview_health import (
            ColumnStatsEngine,
            DatasetPreviewViewsEngine,
            DataHealthCheckEngine,
        )
        ColumnStatsEngine.get_instance()._stats = []
        ColumnStatsEngine.get_instance()._lock = threading.Lock()
        DatasetPreviewViewsEngine.get_instance()._views = []
        DatasetPreviewViewsEngine.get_instance()._lock = threading.Lock()
        DataHealthCheckEngine.get_instance()._checks = []
        DataHealthCheckEngine.get_instance()._lock = threading.Lock()

    def _make_stats(self, **kw: Any) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "dataset_rid": "ds-1",
            "column_name": "col_a",
            "null_count": 0,
            "null_percent": 0.0,
            "distinct_count": 5,
            "distinct_percent": 50.0,
            "min_value": "1",
            "max_value": "10",
            "mean": 5.5,
            "median": 5.0,
            "std_dev": 2.5,
            "sample_values": [1, 2, 3],
            "data_type": "integer",
            "total_rows": 100,
        }
        defaults.update(kw)
        return defaults

    def test_compute_stats_success(self) -> None:
        resp = client.post("/dataset-preview-health/column-stats", json=self._make_stats(), headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats_id"].startswith("cs-")
        assert data["dataset_rid"] == "ds-1"
        assert data["column_name"] == "col_a"

    def test_compute_stats_missing_dataset(self) -> None:
        resp = client.post("/dataset-preview-health/column-stats", json=self._make_stats(dataset_rid=""), headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "MISSING_DATASET"

    def test_compute_stats_missing_column(self) -> None:
        resp = client.post("/dataset-preview-health/column-stats", json=self._make_stats(column_name=""), headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "MISSING_COLUMN"

    def test_get_stats_success(self) -> None:
        created = client.post("/dataset-preview-health/column-stats", json=self._make_stats(), headers=_H)
        stats_id = created.json()["stats_id"]
        resp = client.get(f"/dataset-preview-health/column-stats/{stats_id}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["stats_id"] == stats_id

    def test_get_stats_not_found(self) -> None:
        resp = client.get("/dataset-preview-health/column-stats/cs-nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    def test_list_stats_default(self) -> None:
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(), headers=_H)
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(column_name="col_b"), headers=_H)
        resp = client.get("/dataset-preview-health/column-stats", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_stats_filter_dataset_rid(self) -> None:
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(dataset_rid="ds-1"), headers=_H)
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(dataset_rid="ds-2"), headers=_H)
        resp = client.get("/dataset-preview-health/column-stats?dataset_rid=ds-1", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["dataset_rid"] == "ds-1"

    def test_list_stats_filter_column_name(self) -> None:
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(column_name="col_a"), headers=_H)
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(column_name="col_b"), headers=_H)
        resp = client.get("/dataset-preview-health/column-stats?column_name=col_a", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["column_name"] == "col_a"

    def test_list_stats_filter_data_type(self) -> None:
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(data_type="integer"), headers=_H)
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(data_type="string"), headers=_H)
        resp = client.get("/dataset-preview-health/column-stats?data_type=string", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["data_type"] == "string"

    def test_list_stats_no_match(self) -> None:
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(), headers=_H)
        resp = client.get("/dataset-preview-health/column-stats?dataset_rid=ds-none", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_delete_stats_success(self) -> None:
        created = client.post("/dataset-preview-health/column-stats", json=self._make_stats(), headers=_H)
        stats_id = created.json()["stats_id"]
        resp = client.delete(f"/dataset-preview-health/column-stats/{stats_id}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_stats_not_found(self) -> None:
        resp = client.delete("/dataset-preview-health/column-stats/cs-nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    def test_stats_200_limit_eviction(self) -> None:
        for i in range(205):
            client.post("/dataset-preview-health/column-stats", json=self._make_stats(column_name=f"col_{i}"), headers=_H)
        resp = client.get("/dataset-preview-health/column-stats", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 200

    def test_compute_stats_with_optional_fields(self) -> None:
        payload = {
            "dataset_rid": "ds-1",
            "column_name": "col_opt",
            "null_count": 10,
            "total_rows": 1000,
        }
        resp = client.post("/dataset-preview-health/column-stats", json=payload, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mean"] is None
        assert data["median"] is None
        assert data["std_dev"] is None
        assert data["min_value"] is None
        assert data["max_value"] is None

    def test_list_stats_multiple_filters(self) -> None:
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(dataset_rid="ds-1", column_name="col_a", data_type="integer"), headers=_H)
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(dataset_rid="ds-1", column_name="col_a", data_type="string"), headers=_H)
        client.post("/dataset-preview-health/column-stats", json=self._make_stats(dataset_rid="ds-2", column_name="col_a", data_type="integer"), headers=_H)
        resp = client.get("/dataset-preview-health/column-stats?dataset_rid=ds-1&column_name=col_a&data_type=integer", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_stats_returns_correct_fields(self) -> None:
        resp = client.post("/dataset-preview-health/column-stats", json=self._make_stats(), headers=_H)
        stats_id = resp.json()["stats_id"]
        get_resp = client.get(f"/dataset-preview-health/column-stats/{stats_id}", headers=_H)
        data = get_resp.json()
        assert "stats_id" in data
        assert "dataset_rid" in data
        assert "column_name" in data
        assert "null_count" in data
        assert "null_percent" in data
        assert "distinct_count" in data
        assert "distinct_percent" in data
        assert "min_value" in data
        assert "max_value" in data
        assert "mean" in data
        assert "median" in data
        assert "std_dev" in data
        assert "sample_values" in data
        assert "data_type" in data
        assert "total_rows" in data
        assert "last_computed_at" in data

    def test_delete_stats_idempotent(self) -> None:
        created = client.post("/dataset-preview-health/column-stats", json=self._make_stats(), headers=_H)
        stats_id = created.json()["stats_id"]
        client.delete(f"/dataset-preview-health/column-stats/{stats_id}", headers=_H)
        resp = client.get(f"/dataset-preview-health/column-stats/{stats_id}", headers=_H)
        assert resp.status_code == 404

    def test_list_stats_empty(self) -> None:
        resp = client.get("/dataset-preview-health/column-stats", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []


# ════════════════════ DatasetPreviewViewsEngine ════════════════════

class TestPreviewViews:
    def setup_method(self) -> None:
        from aos_api.dataset_preview_health import (
            ColumnStatsEngine,
            DatasetPreviewViewsEngine,
            DataHealthCheckEngine,
        )
        ColumnStatsEngine.get_instance()._stats = []
        ColumnStatsEngine.get_instance()._lock = threading.Lock()
        DatasetPreviewViewsEngine.get_instance()._views = []
        DatasetPreviewViewsEngine.get_instance()._lock = threading.Lock()
        DataHealthCheckEngine.get_instance()._checks = []
        DataHealthCheckEngine.get_instance()._lock = threading.Lock()

    def _make_view(self, **kw: Any) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "dataset_rid": "ds-1",
            "view_type": "table",
            "config_data": {"limit": 100},
            "enabled": True,
        }
        defaults.update(kw)
        return defaults

    def test_register_view_success(self) -> None:
        resp = client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["view_id"].startswith("pv-")
        assert data["dataset_rid"] == "ds-1"
        assert data["view_type"] == "table"

    def test_register_view_missing_dataset(self) -> None:
        resp = client.post("/dataset-preview-health/preview-views", json=self._make_view(dataset_rid=""), headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "MISSING_DATASET"

    def test_register_view_invalid_view_type(self) -> None:
        resp = client.post("/dataset-preview-health/preview-views", json=self._make_view(view_type="invalid"), headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_VIEW_TYPE"

    def test_get_view_success(self) -> None:
        created = client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        view_id = created.json()["view_id"]
        resp = client.get(f"/dataset-preview-health/preview-views/{view_id}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["view_id"] == view_id

    def test_get_view_not_found(self) -> None:
        resp = client.get("/dataset-preview-health/preview-views/pv-nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    def test_list_views_default(self) -> None:
        client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        client.post("/dataset-preview-health/preview-views", json=self._make_view(view_type="chart"), headers=_H)
        resp = client.get("/dataset-preview-health/preview-views", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_views_filter_dataset_rid(self) -> None:
        client.post("/dataset-preview-health/preview-views", json=self._make_view(dataset_rid="ds-1"), headers=_H)
        client.post("/dataset-preview-health/preview-views", json=self._make_view(dataset_rid="ds-2"), headers=_H)
        resp = client.get("/dataset-preview-health/preview-views?dataset_rid=ds-1", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["dataset_rid"] == "ds-1"

    def test_list_views_filter_view_type(self) -> None:
        client.post("/dataset-preview-health/preview-views", json=self._make_view(view_type="table"), headers=_H)
        client.post("/dataset-preview-health/preview-views", json=self._make_view(view_type="chart"), headers=_H)
        resp = client.get("/dataset-preview-health/preview-views?view_type=chart", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["view_type"] == "chart"

    def test_list_views_filter_enabled(self) -> None:
        client.post("/dataset-preview-health/preview-views", json=self._make_view(enabled=True), headers=_H)
        client.post("/dataset-preview-health/preview-views", json=self._make_view(enabled=False), headers=_H)
        resp = client.get("/dataset-preview-health/preview-views?enabled=true", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["enabled"] is True

    def test_list_views_filter_enabled_false(self) -> None:
        client.post("/dataset-preview-health/preview-views", json=self._make_view(enabled=True), headers=_H)
        client.post("/dataset-preview-health/preview-views", json=self._make_view(enabled=False), headers=_H)
        resp = client.get("/dataset-preview-health/preview-views?enabled=false", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["enabled"] is False

    def test_list_views_no_match(self) -> None:
        client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        resp = client.get("/dataset-preview-health/preview-views?dataset_rid=ds-none", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_update_view_success(self) -> None:
        created = client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        view_id = created.json()["view_id"]
        resp = client.put(f"/dataset-preview-health/preview-views/{view_id}", json={"enabled": False, "config_data": {"limit": 50}}, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["config_data"] == {"limit": 50}

    def test_update_view_invalid_view_type(self) -> None:
        created = client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        view_id = created.json()["view_id"]
        resp = client.put(f"/dataset-preview-health/preview-views/{view_id}", json={"view_type": "invalid"}, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_VIEW_TYPE"

    def test_delete_view_success(self) -> None:
        created = client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        view_id = created.json()["view_id"]
        resp = client.delete(f"/dataset-preview-health/preview-views/{view_id}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_view_not_found(self) -> None:
        resp = client.delete("/dataset-preview-health/preview-views/pv-nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    def test_views_200_limit_eviction(self) -> None:
        for i in range(205):
            client.post("/dataset-preview-health/preview-views", json=self._make_view(dataset_rid=f"ds-{i}"), headers=_H)
        resp = client.get("/dataset-preview-health/preview-views", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 200

    def test_register_view_default_enabled(self) -> None:
        resp = client.post("/dataset-preview-health/preview-views", json={"dataset_rid": "ds-1", "view_type": "table"}, headers=_H)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_update_view_updates_updated_at(self) -> None:
        created = client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        view_id = created.json()["view_id"]
        original_updated_at = created.json()["updated_at"]
        resp = client.put(f"/dataset-preview-health/preview-views/{view_id}", json={"enabled": False}, headers=_H)
        assert resp.status_code == 200
        assert resp.json()["updated_at"] > original_updated_at

    def test_list_views_combined_filters(self) -> None:
        client.post("/dataset-preview-health/preview-views", json=self._make_view(dataset_rid="ds-1", view_type="table", enabled=True), headers=_H)
        client.post("/dataset-preview-health/preview-views", json=self._make_view(dataset_rid="ds-1", view_type="table", enabled=False), headers=_H)
        client.post("/dataset-preview-health/preview-views", json=self._make_view(dataset_rid="ds-1", view_type="chart", enabled=True), headers=_H)
        resp = client.get("/dataset-preview-health/preview-views?dataset_rid=ds-1&view_type=table&enabled=true", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_view_idempotent(self) -> None:
        created = client.post("/dataset-preview-health/preview-views", json=self._make_view(), headers=_H)
        view_id = created.json()["view_id"]
        client.delete(f"/dataset-preview-health/preview-views/{view_id}", headers=_H)
        resp = client.get(f"/dataset-preview-health/preview-views/{view_id}", headers=_H)
        assert resp.status_code == 404

    def test_list_views_empty(self) -> None:
        resp = client.get("/dataset-preview-health/preview-views", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []


# ════════════════════ DataHealthCheckEngine ════════════════════

class TestDataHealthCheck:
    def setup_method(self) -> None:
        from aos_api.dataset_preview_health import (
            ColumnStatsEngine,
            DatasetPreviewViewsEngine,
            DataHealthCheckEngine,
        )
        ColumnStatsEngine.get_instance()._stats = []
        ColumnStatsEngine.get_instance()._lock = threading.Lock()
        DatasetPreviewViewsEngine.get_instance()._views = []
        DatasetPreviewViewsEngine.get_instance()._lock = threading.Lock()
        DataHealthCheckEngine.get_instance()._checks = []
        DataHealthCheckEngine.get_instance()._lock = threading.Lock()

    def _make_check(self, **kw: Any) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "dataset_rid": "ds-1",
            "check_type": "freshness",
            "config": {"threshold": 3600},
            "status": "pending",
            "severity": "warning",
        }
        defaults.update(kw)
        return defaults

    def test_register_check_success(self) -> None:
        resp = client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["check_id"].startswith("hc-")
        assert data["dataset_rid"] == "ds-1"
        assert data["check_type"] == "freshness"

    def test_register_check_missing_dataset(self) -> None:
        resp = client.post("/dataset-preview-health/health-checks", json=self._make_check(dataset_rid=""), headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "MISSING_DATASET"

    def test_register_check_invalid_check_type(self) -> None:
        resp = client.post("/dataset-preview-health/health-checks", json=self._make_check(check_type="invalid"), headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_CHECK_TYPE"

    def test_register_check_invalid_status(self) -> None:
        resp = client.post("/dataset-preview-health/health-checks", json=self._make_check(status="invalid"), headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_STATUS"

    def test_register_check_invalid_severity(self) -> None:
        resp = client.post("/dataset-preview-health/health-checks", json=self._make_check(severity="invalid"), headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_SEVERITY"

    def test_get_check_success(self) -> None:
        created = client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        check_id = created.json()["check_id"]
        resp = client.get(f"/dataset-preview-health/health-checks/{check_id}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["check_id"] == check_id

    def test_get_check_not_found(self) -> None:
        resp = client.get("/dataset-preview-health/health-checks/hc-nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    def test_list_checks_default(self) -> None:
        client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        client.post("/dataset-preview-health/health-checks", json=self._make_check(check_type="volume"), headers=_H)
        resp = client.get("/dataset-preview-health/health-checks", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_checks_filter_dataset_rid(self) -> None:
        client.post("/dataset-preview-health/health-checks", json=self._make_check(dataset_rid="ds-1"), headers=_H)
        client.post("/dataset-preview-health/health-checks", json=self._make_check(dataset_rid="ds-2"), headers=_H)
        resp = client.get("/dataset-preview-health/health-checks?dataset_rid=ds-1", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["dataset_rid"] == "ds-1"

    def test_list_checks_filter_check_type(self) -> None:
        client.post("/dataset-preview-health/health-checks", json=self._make_check(check_type="freshness"), headers=_H)
        client.post("/dataset-preview-health/health-checks", json=self._make_check(check_type="volume"), headers=_H)
        resp = client.get("/dataset-preview-health/health-checks?check_type=volume", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["check_type"] == "volume"

    def test_list_checks_filter_status(self) -> None:
        client.post("/dataset-preview-health/health-checks", json=self._make_check(status="pending"), headers=_H)
        client.post("/dataset-preview-health/health-checks", json=self._make_check(status="passed"), headers=_H)
        resp = client.get("/dataset-preview-health/health-checks?status=passed", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["status"] == "passed"

    def test_list_checks_filter_severity(self) -> None:
        client.post("/dataset-preview-health/health-checks", json=self._make_check(severity="warning"), headers=_H)
        client.post("/dataset-preview-health/health-checks", json=self._make_check(severity="critical"), headers=_H)
        resp = client.get("/dataset-preview-health/health-checks?severity=critical", headers=_H)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["severity"] == "critical"

    def test_list_checks_no_match(self) -> None:
        client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        resp = client.get("/dataset-preview-health/health-checks?dataset_rid=ds-none", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_update_check_success(self) -> None:
        created = client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        check_id = created.json()["check_id"]
        resp = client.put(f"/dataset-preview-health/health-checks/{check_id}", json={"status": "passed", "severity": "critical"}, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "passed"
        assert data["severity"] == "critical"

    def test_update_check_invalid_status(self) -> None:
        created = client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        check_id = created.json()["check_id"]
        resp = client.put(f"/dataset-preview-health/health-checks/{check_id}", json={"status": "invalid"}, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_STATUS"

    def test_update_check_invalid_severity(self) -> None:
        created = client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        check_id = created.json()["check_id"]
        resp = client.put(f"/dataset-preview-health/health-checks/{check_id}", json={"severity": "invalid"}, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_SEVERITY"

    def test_delete_check_success(self) -> None:
        created = client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        check_id = created.json()["check_id"]
        resp = client.delete(f"/dataset-preview-health/health-checks/{check_id}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_check_not_found(self) -> None:
        resp = client.delete("/dataset-preview-health/health-checks/hc-nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    def test_run_check_success(self) -> None:
        created = client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        check_id = created.json()["check_id"]
        resp = client.post(f"/dataset-preview-health/health-checks/{check_id}/run", headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "passed"
        assert data["last_run_at"] is not None
        assert data["last_result"] is not None

    def test_run_check_not_found(self) -> None:
        resp = client.post("/dataset-preview-health/health-checks/hc-nonexistent/run", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    def test_checks_200_limit_eviction(self) -> None:
        for i in range(205):
            client.post("/dataset-preview-health/health-checks", json=self._make_check(dataset_rid=f"ds-{i}"), headers=_H)
        resp = client.get("/dataset-preview-health/health-checks", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 200

    def test_list_checks_combined_filters(self) -> None:
        client.post("/dataset-preview-health/health-checks", json=self._make_check(dataset_rid="ds-1", check_type="freshness", status="pending", severity="warning"), headers=_H)
        client.post("/dataset-preview-health/health-checks", json=self._make_check(dataset_rid="ds-1", check_type="freshness", status="passed", severity="warning"), headers=_H)
        client.post("/dataset-preview-health/health-checks", json=self._make_check(dataset_rid="ds-1", check_type="volume", status="pending", severity="warning"), headers=_H)
        resp = client.get("/dataset-preview-health/health-checks?dataset_rid=ds-1&check_type=freshness&status=pending&severity=warning", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_check_idempotent(self) -> None:
        created = client.post("/dataset-preview-health/health-checks", json=self._make_check(), headers=_H)
        check_id = created.json()["check_id"]
        client.delete(f"/dataset-preview-health/health-checks/{check_id}", headers=_H)
        resp = client.get(f"/dataset-preview-health/health-checks/{check_id}", headers=_H)
        assert resp.status_code == 404

    def test_list_checks_empty(self) -> None:
        resp = client.get("/dataset-preview-health/health-checks", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []
