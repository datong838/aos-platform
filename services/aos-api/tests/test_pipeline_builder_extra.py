"""W2-AZ · Pipeline Builder Extra 单元测试。"""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.pipeline_builder_extra import (
    PipelineBranchEngine,
    PipelineDataExpectationEngine,
    PipelineManagementEngine,
)

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-pbe",
}


class TestPipelineBranchEngine:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        fresh = PipelineBranchEngine()
        monkeypatch.setattr("aos_api.pipeline_builder_extra._branch_engine", fresh)
        monkeypatch.setattr("aos_api.pipeline_builder_extra.PipelineBranchEngine._instance", None)

    def test_create_branch(self, client):
        resp = client.post("/pipeline-builder-extra/branches", json={
            "pipeline_id": "p1",
            "name": "feature-1",
        }, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["branch_id"] is not None
        assert data["pipeline_id"] == "p1"
        assert data["name"] == "feature-1"
        assert data["status"] == "draft"

    def test_create_branch_missing_pipeline(self, client):
        resp = client.post("/pipeline-builder-extra/branches", json={
            "pipeline_id": "",
            "name": "feature-1",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_PIPELINE"

    def test_create_branch_missing_name(self, client):
        resp = client.post("/pipeline-builder-extra/branches", json={
            "pipeline_id": "p1",
            "name": "",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_NAME"

    def test_get_branch(self, client):
        create = client.post("/pipeline-builder-extra/branches", json={
            "pipeline_id": "p1",
            "name": "feature-1",
        }, headers=_H)
        bid = create.json()["branch_id"]
        resp = client.get(f"/pipeline-builder-extra/branches/{bid}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["branch_id"] == bid

    def test_get_branch_not_found(self, client):
        resp = client.get("/pipeline-builder-extra/branches/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_list_branches_empty(self, client):
        resp = client.get("/pipeline-builder-extra/branches", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_branches(self, client):
        client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b2"}, headers=_H)
        client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p2", "name": "b3"}, headers=_H)
        resp = client.get("/pipeline-builder-extra/branches", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_branches_filter_pipeline(self, client):
        client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b2"}, headers=_H)
        client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p2", "name": "b3"}, headers=_H)
        resp = client.get("/pipeline-builder-extra/branches?pipeline_id=p1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_branches_filter_status(self, client):
        client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b2"}, headers=_H)
        bid = create.json()["branch_id"]
        client.post(f"/pipeline-builder-extra/branches/{bid}/approve", headers=_H)
        resp = client.get("/pipeline-builder-extra/branches?status=draft", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_update_branch(self, client):
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        bid = create.json()["branch_id"]
        resp = client.put(f"/pipeline-builder-extra/branches/{bid}?name=updated", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"

    def test_update_branch_not_found(self, client):
        resp = client.put("/pipeline-builder-extra/branches/nonexistent?name=updated", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_delete_branch(self, client):
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        bid = create.json()["branch_id"]
        resp = client.delete(f"/pipeline-builder-extra/branches/{bid}", headers=_H)
        assert resp.status_code == 200
        get_resp = client.get(f"/pipeline-builder-extra/branches/{bid}", headers=_H)
        assert get_resp.status_code == 404

    def test_delete_branch_not_found(self, client):
        resp = client.delete("/pipeline-builder-extra/branches/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_approve_branch_draft(self, client):
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        bid = create.json()["branch_id"]
        resp = client.post(f"/pipeline-builder-extra/branches/{bid}/approve", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_approve_branch_invalid_status(self, client):
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        bid = create.json()["branch_id"]
        client.post(f"/pipeline-builder-extra/branches/{bid}/approve", headers=_H)
        client.post(f"/pipeline-builder-extra/branches/{bid}/merge", json={"target_branch_id": "main"}, headers=_H)
        resp = client.post(f"/pipeline-builder-extra/branches/{bid}/approve", headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_STATUS"

    def test_merge_branch_approved(self, client):
        target = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "main"}, headers=_H)
        target_bid = target.json()["branch_id"]
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        bid = create.json()["branch_id"]
        client.post(f"/pipeline-builder-extra/branches/{bid}/approve", headers=_H)
        resp = client.post(f"/pipeline-builder-extra/branches/{bid}/merge", json={"target_branch_id": target_bid}, headers=_H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "merged"

    def test_merge_branch_invalid_status(self, client):
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        bid = create.json()["branch_id"]
        resp = client.post(f"/pipeline-builder-extra/branches/{bid}/merge", json={"target_branch_id": "main"}, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_STATUS"

    def test_revert_branch_merged(self, client):
        target = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "main"}, headers=_H)
        target_bid = target.json()["branch_id"]
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        bid = create.json()["branch_id"]
        client.post(f"/pipeline-builder-extra/branches/{bid}/approve", headers=_H)
        client.post(f"/pipeline-builder-extra/branches/{bid}/merge", json={"target_branch_id": target_bid}, headers=_H)
        resp = client.post(f"/pipeline-builder-extra/branches/{bid}/revert", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "reverted"

    def test_revert_branch_invalid_status(self, client):
        create = client.post("/pipeline-builder-extra/branches", json={"pipeline_id": "p1", "name": "b1"}, headers=_H)
        bid = create.json()["branch_id"]
        resp = client.post(f"/pipeline-builder-extra/branches/{bid}/revert", headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_STATUS"


class TestPipelineManagementEngine:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        fresh = PipelineManagementEngine()
        monkeypatch.setattr("aos_api.pipeline_builder_extra._management_engine", fresh)
        monkeypatch.setattr("aos_api.pipeline_builder_extra.PipelineManagementEngine._instance", None)

    def test_create_config(self, client):
        resp = client.post("/pipeline-builder-extra/configs", json={
            "pipeline_id": "p1",
            "checkpoints": {"enabled": True},
        }, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_id"] is not None
        assert data["pipeline_id"] == "p1"
        assert data["checkpoints"] == {"enabled": True}

    def test_create_config_missing_pipeline(self, client):
        resp = client.post("/pipeline-builder-extra/configs", json={
            "pipeline_id": "",
            "checkpoints": {"enabled": True},
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_PIPELINE"

    def test_get_config(self, client):
        create = client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p1"}, headers=_H)
        cid = create.json()["config_id"]
        resp = client.get(f"/pipeline-builder-extra/configs/{cid}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["config_id"] == cid

    def test_get_config_not_found(self, client):
        resp = client.get("/pipeline-builder-extra/configs/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_get_config_by_pipeline(self, client):
        client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p1"}, headers=_H)
        client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p1"}, headers=_H)
        client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p2"}, headers=_H)
        resp = client.get("/pipeline-builder-extra/configs/by-pipeline/p1", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["pipeline_id"] == "p1"

    def test_get_config_by_pipeline_empty(self, client):
        resp = client.get("/pipeline-builder-extra/configs/by-pipeline/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_list_configs_empty(self, client):
        resp = client.get("/pipeline-builder-extra/configs", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_configs(self, client):
        client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p1"}, headers=_H)
        client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p2"}, headers=_H)
        resp = client.get("/pipeline-builder-extra/configs", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_configs_filter_pipeline(self, client):
        client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p1"}, headers=_H)
        client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p1"}, headers=_H)
        client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p2"}, headers=_H)
        resp = client.get("/pipeline-builder-extra/configs?pipeline_id=p1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_config(self, client):
        create = client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p1"}, headers=_H)
        cid = create.json()["config_id"]
        resp = client.put(f"/pipeline-builder-extra/configs/{cid}", json={
            "checkpoints": {"enabled": False},
            "parameters": {"max_rows": 1000},
        }, headers=_H)
        assert resp.status_code == 200
        assert resp.json()["checkpoints"] == {"enabled": False}
        assert resp.json()["parameters"] == {"max_rows": 1000}

    def test_update_config_not_found(self, client):
        resp = client.put("/pipeline-builder-extra/configs/nonexistent", json={
            "checkpoints": {"enabled": False},
        }, headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_delete_config(self, client):
        create = client.post("/pipeline-builder-extra/configs", json={"pipeline_id": "p1"}, headers=_H)
        cid = create.json()["config_id"]
        resp = client.delete(f"/pipeline-builder-extra/configs/{cid}", headers=_H)
        assert resp.status_code == 200
        get_resp = client.get(f"/pipeline-builder-extra/configs/{cid}", headers=_H)
        assert get_resp.status_code == 404

    def test_delete_config_not_found(self, client):
        resp = client.delete("/pipeline-builder-extra/configs/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_create_config_with_all_fields(self, client):
        resp = client.post("/pipeline-builder-extra/configs", json={
            "pipeline_id": "p1",
            "checkpoints": {"enabled": True},
            "color_groups": {"g1": "#FF0000"},
            "custom_functions": {"fn1": "code"},
            "folders": {"f1": "path"},
            "sampling_config": {"rate": 0.1},
            "task_groups": {"tg1": ["t1", "t2"]},
            "parameters": {"key": "value"},
        }, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["color_groups"] == {"g1": "#FF0000"}
        assert data["custom_functions"] == {"fn1": "code"}
        assert data["task_groups"] == {"tg1": ["t1", "t2"]}


class TestPipelineDataExpectationEngine:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        fresh = PipelineDataExpectationEngine()
        monkeypatch.setattr("aos_api.pipeline_builder_extra._expectation_engine", fresh)
        monkeypatch.setattr("aos_api.pipeline_builder_extra.PipelineDataExpectationEngine._instance", None)

    def test_create_expectation(self, client):
        resp = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1",
            "name": "pk-check",
            "expectation_type": "primary_key",
            "config": {"column": "id"},
        }, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["expectation_id"] is not None
        assert data["name"] == "pk-check"
        assert data["expectation_type"] == "primary_key"
        assert data["severity"] == "warning"
        assert data["enabled"] is True

    def test_create_expectation_missing_pipeline(self, client):
        resp = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "",
            "name": "test",
            "expectation_type": "row_count",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_PIPELINE"

    def test_create_expectation_missing_name(self, client):
        resp = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1",
            "name": "",
            "expectation_type": "row_count",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_NAME"

    def test_create_expectation_invalid_type(self, client):
        resp = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1",
            "name": "test",
            "expectation_type": "invalid_type",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_EXPECTATION_TYPE"

    def test_create_expectation_invalid_severity(self, client):
        resp = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1",
            "name": "test",
            "expectation_type": "row_count",
            "severity": "invalid_severity",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_SEVERITY"

    def test_get_expectation(self, client):
        create = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1",
            "name": "test",
            "expectation_type": "row_count",
        }, headers=_H)
        eid = create.json()["expectation_id"]
        resp = client.get(f"/pipeline-builder-extra/expectations/{eid}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["expectation_id"] == eid

    def test_get_expectation_not_found(self, client):
        resp = client.get("/pipeline-builder-extra/expectations/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_list_expectations_empty(self, client):
        resp = client.get("/pipeline-builder-extra/expectations", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_expectations(self, client):
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "row_count"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e2", "expectation_type": "primary_key"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p2", "name": "e3", "expectation_type": "row_count"
        }, headers=_H)
        resp = client.get("/pipeline-builder-extra/expectations", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_expectations_filter_pipeline(self, client):
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "row_count"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e2", "expectation_type": "primary_key"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p2", "name": "e3", "expectation_type": "row_count"
        }, headers=_H)
        resp = client.get("/pipeline-builder-extra/expectations?pipeline_id=p1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_expectations_filter_type(self, client):
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "row_count"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e2", "expectation_type": "primary_key"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p2", "name": "e3", "expectation_type": "row_count"
        }, headers=_H)
        resp = client.get("/pipeline-builder-extra/expectations?expectation_type=row_count", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_expectations_filter_enabled(self, client):
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "row_count", "enabled": True
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e2", "expectation_type": "primary_key", "enabled": False
        }, headers=_H)
        resp = client.get("/pipeline-builder-extra/expectations?enabled=true", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_expectations_filter_severity(self, client):
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "row_count", "severity": "critical"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e2", "expectation_type": "primary_key", "severity": "warning"
        }, headers=_H)
        resp = client.get("/pipeline-builder-extra/expectations?severity=warning", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_update_expectation(self, client):
        create = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "row_count"
        }, headers=_H)
        eid = create.json()["expectation_id"]
        resp = client.put(f"/pipeline-builder-extra/expectations/{eid}?name=updated&severity=critical&enabled=false", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"
        assert resp.json()["severity"] == "critical"
        assert resp.json()["enabled"] is False

    def test_update_expectation_not_found(self, client):
        resp = client.put("/pipeline-builder-extra/expectations/nonexistent?name=updated", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_delete_expectation(self, client):
        create = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "row_count"
        }, headers=_H)
        eid = create.json()["expectation_id"]
        resp = client.delete(f"/pipeline-builder-extra/expectations/{eid}", headers=_H)
        assert resp.status_code == 200
        get_resp = client.get(f"/pipeline-builder-extra/expectations/{eid}", headers=_H)
        assert get_resp.status_code == 404

    def test_delete_expectation_not_found(self, client):
        resp = client.delete("/pipeline-builder-extra/expectations/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_run_expectation(self, client):
        create = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "primary_key"
        }, headers=_H)
        eid = create.json()["expectation_id"]
        resp = client.post(f"/pipeline-builder-extra/expectations/{eid}/run", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["last_result"] == "passed"

    def test_run_expectation_not_found(self, client):
        resp = client.post("/pipeline-builder-extra/expectations/nonexistent/run", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_run_expectation_row_count(self, client):
        create = client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "row_count"
        }, headers=_H)
        eid = create.json()["expectation_id"]
        resp = client.post(f"/pipeline-builder-extra/expectations/{eid}/run", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["last_result"] == "failed"

    def test_run_all_expectations(self, client):
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e1", "expectation_type": "primary_key"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p1", "name": "e2", "expectation_type": "row_count"
        }, headers=_H)
        client.post("/pipeline-builder-extra/expectations", json={
            "pipeline_id": "p2", "name": "e3", "expectation_type": "row_count"
        }, headers=_H)
        resp = client.post("/pipeline-builder-extra/expectations/run-all/p1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_run_all_expectations_empty(self, client):
        resp = client.post("/pipeline-builder-extra/expectations/run-all/nonexistent", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []