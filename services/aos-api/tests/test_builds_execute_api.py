"""搭建页面功能测试：管道执行API + 构建日志API."""
from __future__ import annotations

import pytest


@pytest.fixture()
def sample_pipeline(client, auth_headers):
    """创建一个测试管道."""
    r = client.post(
        "/v1/pipelines",
        headers=auth_headers,
        json={
            "id": "test-build-pipeline",
            "sourceId": "file-1",
            "target": "dataset",
            "name": "测试-店铺管道",
            "displayName": "测试-店铺管道",
            "objectTypeHint": "Shop",
        },
    )
    assert r.status_code == 200
    return r.json()


class TestPipelineExecuteApi:
    """POST /v1/pipelines/{id}/execute 执行管道接口."""

    def test_execute_pipeline_not_found(self, client, auth_headers):
        """执行不存在的管道应返回 404."""
        r = client.post(
            "/v1/pipelines/nonexistent-pipeline/execute",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 404
        body = r.json()
        # ApiError 格式为 {"code": "...", "message": "..."}；默认 FastAPI 404 是 {"detail": "..."}
        assert body.get("code") == "NOT_FOUND" or body.get("detail") is not None

    def test_execute_pipeline_success(self, client, auth_headers, sample_pipeline):
        """执行存在的管道应返回构建信息，包含状态、日志、耗时等."""
        pl_id = sample_pipeline["id"]
        r = client.post(
            f"/v1/pipelines/{pl_id}/execute",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200
        body = r.json()
        # 构建ID存在
        assert "buildId" in body
        # 状态应为 SUCCEEDED 或 RUNNING（同步执行直接返回成功）
        assert body["status"] in ("RUNNING", "SUCCEEDED", "FAILED")
        # 必须包含 startedAt
        assert "startedAt" in body
        # 必须包含 pipelineId 和 pipelineName
        assert body["pipelineId"] == pl_id
        assert "pipelineName" in body
        # 任务列表必须有 ingest / transform / sink 三个阶段
        tasks = body.get("tasks", [])
        task_names = [t["name"] for t in tasks]
        assert "ingest" in task_names
        assert "transform" in task_names
        assert "sink" in task_names
        # 必须有日志
        assert "logs" in body
        assert len(body["logs"]) >= 1

    def test_execute_pipeline_updates_lastBuild(self, client, auth_headers, sample_pipeline):
        """执行管道后应更新管道的 lastBuild 字段，list_builds 应能看到新构建."""
        pl_id = sample_pipeline["id"]
        # 先执行
        r = client.post(
            f"/v1/pipelines/{pl_id}/execute",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200
        exec_body = r.json()
        new_build_id = exec_body["buildId"]

        # 再查 builds 列表，应能找到该管道的构建
        r2 = client.get("/v1/builds", headers=auth_headers)
        assert r2.status_code == 200
        builds = r2.json()["items"]
        # 至少找到一个匹配 pipelineId 的构建
        matching = [b for b in builds if b["pipelineId"] == pl_id]
        assert len(matching) >= 1
        # 最新构建的 id 应该是我们刚执行出来的
        assert matching[0]["id"] == new_build_id
        # 构建状态
        assert matching[0]["status"] in ("SUCCEEDED", "RUNNING", "FAILED")


class TestBuildLogsApi:
    """GET /v1/builds/{id}/logs 获取构建日志接口."""

    def test_get_build_logs_not_found(self, client, auth_headers):
        """获取不存在的构建日志应返回 404."""
        r = client.get(
            "/v1/builds/nonexistent-build/logs",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_get_build_logs_success(self, client, auth_headers, sample_pipeline):
        """执行后获取构建日志，应包含时间、级别、消息字段."""
        pl_id = sample_pipeline["id"]
        # 先执行
        r = client.post(
            f"/v1/pipelines/{pl_id}/execute",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200
        build_id = r.json()["buildId"]

        # 再取日志
        r2 = client.get(
            f"/v1/builds/{build_id}/logs",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        body = r2.json()
        assert "items" in body
        logs = body["items"]
        assert len(logs) >= 3  # 至少 3 条日志（ingest/transform/sink 各一条）
        # 每条日志应有时间、级别、消息
        for log in logs:
            assert "time" in log
            assert "level" in log
            assert log["level"] in ("INFO", "WARN", "ERROR", "DEBUG")
            assert "msg" in log


class TestBuildToDatasetPreviewConsistency:
    """端到端自洽：执行管道写入 obj_instance，再从 analytics preview 查必须非空且总数一致."""

    def test_execute_then_preview_total_nonzero(self, client, auth_headers):
        """Bug 2 修复验证：先拿第一个种子管道执行，再查 analytics preview 不应为 0."""
        # 1. 取种子的第一个有 datasetRid 的管道
        r_pl = client.get("/v1/pipelines", headers=auth_headers)
        assert r_pl.status_code == 200
        pipelines = [
            p for p in r_pl.json()["items"]
            if p.get("datasetRid") and p.get("objectTypeHint")
        ]
        if not pipelines:
            pytest.skip("seed 未提供带 datasetRid+objectTypeHint 的管道")
        pl = pipelines[0]
        pl_id = pl["id"]
        ot = pl["objectTypeHint"]
        rid = pl["datasetRid"]
        # 2. 全量模式执行一次：避免增量导致条数波动
        r = client.post(
            f"/v1/pipelines/{pl_id}/execute",
            headers=auth_headers,
            json={"mode": "full"},
        )
        assert r.status_code == 200
        body = r.json()
        rows_written = int(body.get("rowsWritten") or 0)
        assert rows_written > 0, "execute 必须返回大于 0 的 rowsWritten"
        # 3. analytics preview 用 datasetRid 查 -> total 不应为 0
        r_prev = client.post(
            "/v1/analytics/datasets/preview",
            headers=auth_headers,
            json={"datasetRid": rid, "limit": 5},
        )
        assert r_prev.status_code == 200, f"preview API 非 200: {r_prev.text[:200]}"
        prev = r_prev.json()
        total = int(prev.get("total") or 0)
        assert total > 0, (
            f"执行后 analytics preview total=0（管道 {pl_id}，objectTypeHint={ot}），"
            f"sink 未正确写入 PostgreSQL obj_instance"
        )
        assert total == rows_written, (
            f"自洽失败：execute rowsWritten={rows_written} vs preview total={total}"
        )
        # 4. 采样行必须非空且包含语义化字段（至少前几列非空）
        rows = prev.get("rows") or []
        assert len(rows) >= 1, "preview rows 采样必须 >= 1"
        columns = prev.get("columns") or []
        assert len(columns) >= 3, f"预览列太少，mock 字段未写入?: {columns[:5]}"

    def test_execute_logs_contains_sink_pg(self, client, auth_headers, sample_pipeline):
        """日志里必须有 sink-pg 的写入记录（含 object_type 关键字）."""
        # sample_pipeline 有 objectTypeHint=Shop，会走 sink-pg
        pl_id = sample_pipeline["id"]
        r = client.post(
            f"/v1/pipelines/{pl_id}/execute",
            headers=auth_headers,
            json={"mode": "full"},
        )
        assert r.status_code == 200
        logs = r.json().get("logs") or []
        msgs = [l.get("msg", "") for l in logs]
        # 任何一条包含 sink-pg
        assert any("sink-pg" in m for m in msgs), (
            f"日志中缺少 sink-pg 写入记录，实际日志: {msgs[:5]}"
        )
