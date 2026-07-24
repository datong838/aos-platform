"""157 · analytics-runtime dual-mode (shaped path always; no Jupyter required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RT = Path(__file__).resolve().parents[3] / "deploy" / "dev" / "analytics-runtime"


@pytest.fixture()
def shaped_client(monkeypatch):
    monkeypatch.setenv("AOS_ANALYTICS_ENGINE", "shaped")
    sys.path.insert(0, str(RT))
    for k in list(sys.modules):
        if k == "app" or k.startswith("app."):
            del sys.modules[k]
    import app as runtime_app

    from fastapi.testclient import TestClient

    with TestClient(runtime_app.app) as c:
        yield c, runtime_app


def test_shaped_health(shaped_client):
    c, _ = shaped_client
    r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "shaped-dev"
    assert body["notebookUi"] == "notebook7"


def test_shaped_session_ticket_ui(shaped_client):
    c, _ = shaped_client
    r = c.post("/v1/sessions", json={"objectType": "WorkOrder", "purpose": "explore"})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "shaped-dev"
    assert "ticket" in body
    assert "/ui/" in body["uiUrl"]
    ticket = body["ticket"]
    sid = body["id"]
    ui = c.get(f"/ui/{sid}?ticket={ticket}")
    assert ui.status_code == 200
    assert b"shaped" in ui.content.lower() or b"Notebook" in ui.content


def test_shaped_rejects_bad_ticket(shaped_client):
    c, _ = shaped_client
    r = c.post("/v1/sessions", json={})
    sid = r.json()["id"]
    bad = c.get(f"/ui/{sid}?ticket=wrong")
    assert bad.status_code == 403
