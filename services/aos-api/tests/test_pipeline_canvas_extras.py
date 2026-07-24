"""W2-BA · Pipeline Canvas Extras 单元测试."""
from __future__ import annotations

import threading

import pytest

from aos_api.pipeline_canvas_extras import (
    CodeRepositoryEngine,
    MediaSetShardingEngine,
    PipelineCanvasEngine,
    get_canvas_engine,
    get_repo_engine,
    get_sharding_engine,
)

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-pce",
}


class TestPipelineCanvasEngine:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        fresh = PipelineCanvasEngine()
        monkeypatch.setattr("aos_api.pipeline_canvas_extras._canvas_engine", fresh)
        monkeypatch.setattr("aos_api.pipeline_canvas_extras.PipelineCanvasEngine._instance", None)

    def test_create_node(self, client):
        resp = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1",
            "node_type": "transform",
            "name": "Node1",
        }, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_id"] is not None
        assert data["pipeline_id"] == "p1"
        assert data["node_type"] == "transform"
        assert data["name"] == "Node1"
        assert data["status"] == "pending"

    def test_create_node_missing_pipeline(self, client):
        resp = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "",
            "node_type": "transform",
            "name": "Node1",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_PIPELINE"

    def test_create_node_missing_name(self, client):
        resp = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1",
            "node_type": "transform",
            "name": "",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_NAME"

    def test_create_node_invalid_type(self, client):
        resp = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1",
            "node_type": "invalid_type",
            "name": "Node1",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_NODE_TYPE"

    def test_get_node(self, client):
        create = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1",
            "node_type": "input",
            "name": "Source1",
        }, headers=_H)
        nid = create.json()["node_id"]
        resp = client.get(f"/pipeline-canvas-extras/nodes/{nid}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["node_id"] == nid

    def test_get_node_not_found(self, client):
        resp = client.get("/pipeline-canvas-extras/nodes/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_list_nodes_empty(self, client):
        resp = client.get("/pipeline-canvas-extras/nodes", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_nodes(self, client):
        client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "input", "name": "n1"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "transform", "name": "n2"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p2", "node_type": "output", "name": "n3"
        }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/nodes", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_nodes_filter_pipeline(self, client):
        client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "input", "name": "n1"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "transform", "name": "n2"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p2", "node_type": "output", "name": "n3"
        }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/nodes?pipeline_id=p1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_node(self, client):
        create = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "transform", "name": "n1"
        }, headers=_H)
        nid = create.json()["node_id"]
        resp = client.put(f"/pipeline-canvas-extras/nodes/{nid}", json={
            "name": "updated",
            "x": 100.0,
            "y": 200.0,
            "status": "running",
        }, headers=_H)
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"
        assert resp.json()["x"] == 100.0
        assert resp.json()["y"] == 200.0
        assert resp.json()["status"] == "running"

    def test_update_node_not_found(self, client):
        resp = client.put("/pipeline-canvas-extras/nodes/nonexistent", json={
            "name": "updated",
        }, headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_delete_node(self, client):
        create = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "transform", "name": "n1"
        }, headers=_H)
        nid = create.json()["node_id"]
        resp = client.delete(f"/pipeline-canvas-extras/nodes/{nid}", headers=_H)
        assert resp.status_code == 200
        get_resp = client.get(f"/pipeline-canvas-extras/nodes/{nid}", headers=_H)
        assert get_resp.status_code == 404

    def test_delete_node_not_found(self, client):
        resp = client.delete("/pipeline-canvas-extras/nodes/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_create_edge(self, client):
        resp = client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1",
            "source_node_id": "node-a",
            "source_port": "out",
            "target_node_id": "node-b",
            "target_port": "in",
        }, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["edge_id"] is not None
        assert data["edge_type"] == "data"

    def test_create_edge_invalid_type(self, client):
        resp = client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1",
            "source_node_id": "node-a",
            "source_port": "out",
            "target_node_id": "node-b",
            "target_port": "in",
            "edge_type": "invalid",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_EDGE_TYPE"

    def test_create_edge_missing_pipeline(self, client):
        resp = client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "",
            "source_node_id": "node-a",
            "source_port": "out",
            "target_node_id": "node-b",
            "target_port": "in",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_PIPELINE"

    def test_get_edge(self, client):
        create = client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1",
            "source_node_id": "node-a",
            "source_port": "out",
            "target_node_id": "node-b",
            "target_port": "in",
        }, headers=_H)
        eid = create.json()["edge_id"]
        resp = client.get(f"/pipeline-canvas-extras/edges/{eid}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["edge_id"] == eid

    def test_get_edge_not_found(self, client):
        resp = client.get("/pipeline-canvas-extras/edges/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_list_edges(self, client):
        client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1", "source_node_id": "a", "source_port": "out",
            "target_node_id": "b", "target_port": "in"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1", "source_node_id": "b", "source_port": "out",
            "target_node_id": "c", "target_port": "in"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p2", "source_node_id": "x", "source_port": "out",
            "target_node_id": "y", "target_port": "in"
        }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/edges", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_edges_filter_pipeline(self, client):
        client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1", "source_node_id": "a", "source_port": "out",
            "target_node_id": "b", "target_port": "in"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1", "source_node_id": "b", "source_port": "out",
            "target_node_id": "c", "target_port": "in"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p2", "source_node_id": "x", "source_port": "out",
            "target_node_id": "y", "target_port": "in"
        }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/edges?pipeline_id=p1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_edge(self, client):
        create = client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1", "source_node_id": "a", "source_port": "out",
            "target_node_id": "b", "target_port": "in"
        }, headers=_H)
        eid = create.json()["edge_id"]
        resp = client.delete(f"/pipeline-canvas-extras/edges/{eid}", headers=_H)
        assert resp.status_code == 200
        get_resp = client.get(f"/pipeline-canvas-extras/edges/{eid}", headers=_H)
        assert get_resp.status_code == 404

    def test_delete_edge_not_found(self, client):
        resp = client.delete("/pipeline-canvas-extras/edges/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_validate_dag_valid(self, client):
        n1 = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "input", "name": "n1"
        }, headers=_H).json()
        n2 = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "transform", "name": "n2"
        }, headers=_H).json()
        n3 = client.post("/pipeline-canvas-extras/nodes", json={
            "pipeline_id": "p1", "node_type": "output", "name": "n3"
        }, headers=_H).json()
        client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1", "source_node_id": n1["node_id"],
            "source_port": "out", "target_node_id": n2["node_id"],
            "target_port": "in"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/edges", json={
            "pipeline_id": "p1", "source_node_id": n2["node_id"],
            "source_port": "out", "target_node_id": n3["node_id"],
            "target_port": "in"
        }, headers=_H)
        resp = client.post("/pipeline-canvas-extras/validate-dag/p1", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_dag_empty(self, client):
        resp = client.post("/pipeline-canvas-extras/validate-dag/p1", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_node_limit_200(self, client):
        for i in range(201):
            client.post("/pipeline-canvas-extras/nodes", json={
                "pipeline_id": "p1",
                "node_type": "transform",
                "name": f"node-{i}",
            }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/nodes?pipeline_id=p1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 200


class TestCodeRepositoryEngine:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        fresh = CodeRepositoryEngine()
        monkeypatch.setattr("aos_api.pipeline_canvas_extras._repo_engine", fresh)
        monkeypatch.setattr("aos_api.pipeline_canvas_extras.CodeRepositoryEngine._instance", None)

    def test_create_repo(self, client):
        resp = client.post("/pipeline-canvas-extras/repos", json={
            "name": "test-repo",
            "repository_type": "git",
            "location": "https://github.com/test/repo.git",
            "branch": "main",
        }, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["repo_id"] is not None
        assert data["name"] == "test-repo"
        assert data["repository_type"] == "git"
        assert data["status"] == "inactive"

    def test_create_repo_missing_name(self, client):
        resp = client.post("/pipeline-canvas-extras/repos", json={
            "name": "",
            "repository_type": "git",
            "location": "https://github.com/test/repo.git",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_NAME"

    def test_create_repo_missing_location(self, client):
        resp = client.post("/pipeline-canvas-extras/repos", json={
            "name": "test-repo",
            "repository_type": "git",
            "location": "",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_LOCATION"

    def test_create_repo_invalid_type(self, client):
        resp = client.post("/pipeline-canvas-extras/repos", json={
            "name": "test-repo",
            "repository_type": "invalid",
            "location": "https://github.com/test/repo.git",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_REPOSITORY_TYPE"

    def test_get_repo(self, client):
        create = client.post("/pipeline-canvas-extras/repos", json={
            "name": "test-repo",
            "repository_type": "git",
            "location": "https://github.com/test/repo.git",
        }, headers=_H)
        rid = create.json()["repo_id"]
        resp = client.get(f"/pipeline-canvas-extras/repos/{rid}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["repo_id"] == rid

    def test_get_repo_not_found(self, client):
        resp = client.get("/pipeline-canvas-extras/repos/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_list_repos_empty(self, client):
        resp = client.get("/pipeline-canvas-extras/repos", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_repos(self, client):
        client.post("/pipeline-canvas-extras/repos", json={
            "name": "r1", "repository_type": "git", "location": "loc1"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/repos", json={
            "name": "r2", "repository_type": "local", "location": "loc2"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/repos", json={
            "name": "r3", "repository_type": "s3", "location": "loc3"
        }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/repos", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_update_repo(self, client):
        create = client.post("/pipeline-canvas-extras/repos", json={
            "name": "r1", "repository_type": "git", "location": "loc1"
        }, headers=_H)
        rid = create.json()["repo_id"]
        resp = client.put(f"/pipeline-canvas-extras/repos/{rid}", json={
            "name": "updated",
            "branch": "develop",
        }, headers=_H)
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"
        assert resp.json()["branch"] == "develop"

    def test_update_repo_not_found(self, client):
        resp = client.put("/pipeline-canvas-extras/repos/nonexistent", json={
            "name": "updated",
        }, headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_delete_repo(self, client):
        create = client.post("/pipeline-canvas-extras/repos", json={
            "name": "r1", "repository_type": "git", "location": "loc1"
        }, headers=_H)
        rid = create.json()["repo_id"]
        resp = client.delete(f"/pipeline-canvas-extras/repos/{rid}", headers=_H)
        assert resp.status_code == 200
        get_resp = client.get(f"/pipeline-canvas-extras/repos/{rid}", headers=_H)
        assert get_resp.status_code == 404

    def test_delete_repo_not_found(self, client):
        resp = client.delete("/pipeline-canvas-extras/repos/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_sync_repo(self, client):
        create = client.post("/pipeline-canvas-extras/repos", json={
            "name": "r1", "repository_type": "git", "location": "loc1"
        }, headers=_H)
        rid = create.json()["repo_id"]
        resp = client.post(f"/pipeline-canvas-extras/repos/{rid}/sync", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["commit_hash"] is not None
        assert resp.json()["last_sync_at"] is not None
        assert resp.json()["status"] == "active"

    def test_sync_repo_not_found(self, client):
        resp = client.post("/pipeline-canvas-extras/repos/nonexistent/sync", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_list_files(self, client):
        create = client.post("/pipeline-canvas-extras/repos", json={
            "name": "r1", "repository_type": "git", "location": "loc1"
        }, headers=_H)
        rid = create.json()["repo_id"]
        resp = client.get(f"/pipeline-canvas-extras/repos/{rid}/files", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_repo_limit_200(self, client):
        for i in range(201):
            client.post("/pipeline-canvas-extras/repos", json={
                "name": f"repo-{i}",
                "repository_type": "git",
                "location": f"loc-{i}",
            }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/repos", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 200


class TestMediaSetShardingEngine:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        fresh = MediaSetShardingEngine()
        monkeypatch.setattr("aos_api.pipeline_canvas_extras._sharding_engine", fresh)
        monkeypatch.setattr("aos_api.pipeline_canvas_extras.MediaSetShardingEngine._instance", None)

    def test_create_shard(self, client):
        resp = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1",
            "shard_index": 0,
            "total_shards": 3,
            "file_path": "shard0.dat",
            "size_bytes": 1024,
            "checksum": "abc123",
        }, headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["shard_id"] is not None
        assert data["media_set_id"] == "ms1"
        assert data["shard_index"] == 0
        assert data["status"] == "pending"

    def test_create_shard_missing_media_set(self, client):
        resp = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "",
            "shard_index": 0,
            "total_shards": 3,
            "file_path": "shard0.dat",
            "size_bytes": 1024,
            "checksum": "abc123",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "MISSING_MEDIA_SET"

    def test_create_shard_invalid_index(self, client):
        resp = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1",
            "shard_index": 5,
            "total_shards": 3,
            "file_path": "shard5.dat",
            "size_bytes": 1024,
            "checksum": "abc123",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_SHARD_INDEX"

    def test_get_shard(self, client):
        create = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1",
            "shard_index": 0,
            "total_shards": 3,
            "file_path": "shard0.dat",
            "size_bytes": 1024,
            "checksum": "abc123",
        }, headers=_H)
        sid = create.json()["shard_id"]
        resp = client.get(f"/pipeline-canvas-extras/shards/{sid}", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["shard_id"] == sid

    def test_get_shard_not_found(self, client):
        resp = client.get("/pipeline-canvas-extras/shards/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_list_shards_empty(self, client):
        resp = client.get("/pipeline-canvas-extras/shards", headers=_H)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_shards(self, client):
        client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 2,
            "file_path": "s0.dat", "size_bytes": 1024, "checksum": "h0"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 1, "total_shards": 2,
            "file_path": "s1.dat", "size_bytes": 2048, "checksum": "h1"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms2", "shard_index": 0, "total_shards": 1,
            "file_path": "s0.dat", "size_bytes": 512, "checksum": "h2"
        }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/shards", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_shards_filter_media_set(self, client):
        client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 2,
            "file_path": "s0.dat", "size_bytes": 1024, "checksum": "h0"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 1, "total_shards": 2,
            "file_path": "s1.dat", "size_bytes": 2048, "checksum": "h1"
        }, headers=_H)
        client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms2", "shard_index": 0, "total_shards": 1,
            "file_path": "s0.dat", "size_bytes": 512, "checksum": "h2"
        }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/shards?media_set_id=ms1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_shard(self, client):
        create = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 3,
            "file_path": "shard0.dat", "size_bytes": 1024, "checksum": "abc123"
        }, headers=_H)
        sid = create.json()["shard_id"]
        resp = client.put(f"/pipeline-canvas-extras/shards/{sid}", json={
            "status": "uploading",
        }, headers=_H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "uploading"

    def test_update_shard_invalid_status(self, client):
        create = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 3,
            "file_path": "shard0.dat", "size_bytes": 1024, "checksum": "abc123"
        }, headers=_H)
        sid = create.json()["shard_id"]
        resp = client.put(f"/pipeline-canvas-extras/shards/{sid}", json={
            "status": "invalid",
        }, headers=_H)
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_STATUS"

    def test_update_shard_not_found(self, client):
        resp = client.put("/pipeline-canvas-extras/shards/nonexistent", json={
            "status": "uploading",
        }, headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_delete_shard(self, client):
        create = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 3,
            "file_path": "shard0.dat", "size_bytes": 1024, "checksum": "abc123"
        }, headers=_H)
        sid = create.json()["shard_id"]
        resp = client.delete(f"/pipeline-canvas-extras/shards/{sid}", headers=_H)
        assert resp.status_code == 200
        get_resp = client.get(f"/pipeline-canvas-extras/shards/{sid}", headers=_H)
        assert get_resp.status_code == 404

    def test_delete_shard_not_found(self, client):
        resp = client.delete("/pipeline-canvas-extras/shards/nonexistent", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_complete_upload(self, client):
        create = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 3,
            "file_path": "shard0.dat", "size_bytes": 1024, "checksum": "abc123"
        }, headers=_H)
        sid = create.json()["shard_id"]
        resp = client.post(f"/pipeline-canvas-extras/shards/{sid}/complete", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["uploaded_at"] is not None

    def test_complete_upload_not_found(self, client):
        resp = client.post("/pipeline-canvas-extras/shards/nonexistent/complete", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_fail_upload(self, client):
        create = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 3,
            "file_path": "shard0.dat", "size_bytes": 1024, "checksum": "abc123"
        }, headers=_H)
        sid = create.json()["shard_id"]
        resp = client.post(f"/pipeline-canvas-extras/shards/{sid}/fail?error_message=network error", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert resp.json()["error_message"] == "network error"

    def test_fail_upload_not_found(self, client):
        resp = client.post("/pipeline-canvas-extras/shards/nonexistent/fail", headers=_H)
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_get_upload_status(self, client):
        client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 3,
            "file_path": "s0.dat", "size_bytes": 1024, "checksum": "h0"
        }, headers=_H)
        create1 = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 1, "total_shards": 3,
            "file_path": "s1.dat", "size_bytes": 2048, "checksum": "h1"
        }, headers=_H)
        create2 = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 2, "total_shards": 3,
            "file_path": "s2.dat", "size_bytes": 512, "checksum": "h2"
        }, headers=_H)
        client.post(f"/pipeline-canvas-extras/shards/{create1.json()['shard_id']}/complete", headers=_H)
        client.post(f"/pipeline-canvas-extras/shards/{create2.json()['shard_id']}/fail", headers=_H)
        resp = client.get("/pipeline-canvas-extras/shards/upload-status/ms1", headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_shards"] == 3
        assert data["completed_shards"] == 1
        assert data["failed_shards"] == 1
        assert data["pending_shards"] == 1

    def test_get_upload_status_not_found(self, client):
        resp = client.get("/pipeline-canvas-extras/shards/upload-status/nonexistent", headers=_H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_found"

    def test_get_upload_status_complete(self, client):
        create1 = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 0, "total_shards": 2,
            "file_path": "s0.dat", "size_bytes": 1024, "checksum": "h0"
        }, headers=_H)
        create2 = client.post("/pipeline-canvas-extras/shards", json={
            "media_set_id": "ms1", "shard_index": 1, "total_shards": 2,
            "file_path": "s1.dat", "size_bytes": 2048, "checksum": "h1"
        }, headers=_H)
        client.post(f"/pipeline-canvas-extras/shards/{create1.json()['shard_id']}/complete", headers=_H)
        client.post(f"/pipeline-canvas-extras/shards/{create2.json()['shard_id']}/complete", headers=_H)
        resp = client.get("/pipeline-canvas-extras/shards/upload-status/ms1", headers=_H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_shard_limit_200(self, client):
        for i in range(201):
            client.post("/pipeline-canvas-extras/shards", json={
                "media_set_id": "ms1",
                "shard_index": i,
                "total_shards": 201,
                "file_path": f"shard-{i}.dat",
                "size_bytes": 1024,
                "checksum": f"hash-{i}",
            }, headers=_H)
        resp = client.get("/pipeline-canvas-extras/shards?media_set_id=ms1", headers=_H)
        assert resp.status_code == 200
        assert len(resp.json()) == 200