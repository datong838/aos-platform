"""111 · TA.2 Facade session ticket proxy."""

from __future__ import annotations

import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError


def _resp(payload: dict, status: int = 200):
    raw = json.dumps(payload).encode("utf-8")

    class _Resp:
        def __init__(self):
            self.status = status

        def read(self, _n=None):
            return raw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return _Resp()


def _route_open(req, timeout=None):  # noqa: ARG001
    url = req.full_url
    method = (req.get_method() or "GET").upper()
    if url.endswith("/health"):
        return _resp(
            {
                "status": "ok",
                "notebookUi": "notebook7",
                "engine": "shaped-dev",
                "service": "analytics-runtime",
                "mode": "ta2-session",
            }
        )
    if method == "POST" and url.endswith("/v1/sessions"):
        return _resp(
            {
                "id": "nb-test111aaa",
                "status": "idle",
                "uiUrl": "http://127.0.0.1:8084/ui/nb-test111aaa?ticket=tok-abc",
                "ticket": "tok-abc",
                "ticketExpiresAt": "2099-01-01T00:00:00Z",
                "notebookUi": "notebook7",
                "engine": "shaped-dev",
            }
        )
    if method == "DELETE" and "/v1/sessions/" in url:
        return _resp({"id": "nb-test111aaa", "status": "stopped"})
    raise AssertionError(f"unexpected {method} {url}")


def test_create_session_returns_ticketed_ui(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_ANALYTICS_URL", "http://127.0.0.1:8084")
    with patch("aos_api.routers.analytics.urlrequest.urlopen", side_effect=_route_open):
        r = client.post(
            "/v1/notebooks/sessions",
            headers=auth_headers,
            json={"objectType": "WorkOrder", "purpose": "explore"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "nb-test111aaa"
    assert body["status"] == "idle"
    assert "ticket=" in (body.get("uiUrl") or "")
    assert body["ticketExpiresAt"]
    assert body["mode"] == "ta2-ticket"
    assert "ticket" not in body  # must not expose raw ticket field separately if stripped
    # list contains it
    g = client.get("/v1/notebooks/sessions", headers=auth_headers)
    assert g.status_code == 200
    ids = [i.get("id") for i in g.json().get("items") or []]
    assert "nb-test111aaa" in ids


def test_stop_session_revokes_via_sidecar(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_ANALYTICS_URL", "http://127.0.0.1:8084")
    with patch("aos_api.routers.analytics.urlrequest.urlopen", side_effect=_route_open):
        c = client.post(
            "/v1/notebooks/sessions",
            headers=auth_headers,
            json={"purpose": "explore"},
        )
        assert c.status_code == 200
        sid = c.json()["id"]
        d = client.delete(f"/v1/notebooks/sessions/{sid}", headers=auth_headers)
    assert d.status_code == 200
    assert d.json()["status"] == "stopped"


def test_create_session_503_when_ticket_endpoint_fails(client, auth_headers, monkeypatch):
    import io

    monkeypatch.setenv("AOS_ANALYTICS_URL", "http://127.0.0.1:8084")

    def _open(req, timeout=None):  # noqa: ARG001
        url = req.full_url
        if url.endswith("/health"):
            return _resp({"status": "ok"})
        if url.endswith("/v1/sessions"):
            raise HTTPError(
                url,
                500,
                "boom",
                hdrs=None,
                fp=io.BytesIO(b'{"detail":"boom"}'),
            )
        raise URLError("nope")

    with patch("aos_api.routers.analytics.urlrequest.urlopen", side_effect=_open):
        r = client.post(
            "/v1/notebooks/sessions",
            headers=auth_headers,
            json={"purpose": "explore"},
        )
    assert r.status_code == 503
    assert r.json()["code"] == "ANALYTICS_SESSION_TICKET_UNAVAILABLE"


def test_health_sessions_capable(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_ANALYTICS_URL", "http://127.0.0.1:8084")
    with patch("aos_api.routers.analytics.urlrequest.urlopen", side_effect=_route_open):
        r = client.get("/v1/analytics/health", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "ta2-session"
    assert body["sessionsCapable"] is True
