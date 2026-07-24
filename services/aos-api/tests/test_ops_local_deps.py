"""165 — local deps probe / ensure (no docker required for unit path)."""
from __future__ import annotations

import os
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api import mock_data


@pytest.fixture()
def api_client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth() -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_probe_deps_shape(api_client):
    r = api_client.get("/v1/ops/local/deps", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert "ok" in body
    assert "items" in body
    ids = {i["id"] for i in body["items"]}
    assert "pg" in ids
    assert "minio" in ids


def test_ensure_already_up_short_circuits(api_client):
    with mock.patch("aos_api.local_deps.probe_deps") as probe:
        probe.return_value = {
            "ok": True,
            "items": [
                {
                    "id": "pg",
                    "name": "PostgreSQL",
                    "host": "127.0.0.1",
                    "port": 5433,
                    "ok": True,
                    "endpoint": "127.0.0.1:5433",
                },
                {
                    "id": "minio",
                    "name": "MinIO",
                    "host": "127.0.0.1",
                    "port": 9000,
                    "ok": True,
                    "endpoint": "127.0.0.1:9000",
                },
            ],
            "ensureAllowed": True,
        }
        r = api_client.post("/v1/ops/local/deps/ensure", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["action"] == "already_up"
    assert body["ok"] is True


def test_ensure_failed_without_docker(api_client):
    with (
        mock.patch("aos_api.local_deps.probe_deps") as probe,
        mock.patch("aos_api.local_deps._docker_bin", return_value=None),
        mock.patch("aos_api.local_deps.ensure_allowed", return_value=True),
    ):
        probe.return_value = {
            "ok": False,
            "items": [
                {
                    "id": "pg",
                    "name": "PostgreSQL",
                    "host": "127.0.0.1",
                    "port": 5433,
                    "ok": False,
                    "endpoint": "127.0.0.1:5433",
                },
                {
                    "id": "minio",
                    "name": "MinIO",
                    "host": "127.0.0.1",
                    "port": 9000,
                    "ok": False,
                    "endpoint": "127.0.0.1:9000",
                },
            ],
            "ensureAllowed": True,
        }
        r = api_client.post("/v1/ops/local/deps/ensure", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["action"] == "failed"
    assert body["ok"] is False
    assert "docker" in body["message"].lower()


def test_probe_docker_hub_401_is_ok(api_client):
    import urllib.error

    err = urllib.error.HTTPError(
        url="https://registry-1.docker.io/v2/",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )
    with mock.patch("urllib.request.urlopen", side_effect=err):
        r = api_client.get("/v1/ops/local/hub", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "start-local" in body["hint"]


def test_probe_docker_hub_timeout(api_client):
    with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        r = api_client.get("/v1/ops/local/hub", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert "栈已绿可忽略" in body["hint"]
    assert "start-local.ps1" in body["hint"] or "start-local-native" in body["hint"]
