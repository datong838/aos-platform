"""110 · TA.1 analytics-runtime sidecar probe + session ticket gate."""

from __future__ import annotations

from unittest.mock import patch


def test_health_ok_when_sidecar_probes(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_ANALYTICS_URL", "http://127.0.0.1:8084")

    class _Resp:
        def read(self, _n=None):
            return b'{"status":"ok","notebookUi":"notebook7","engine":"shaped-dev","service":"analytics-runtime"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("aos_api.routers.analytics.urlrequest.urlopen", return_value=_Resp()):
        r = client.get("/v1/analytics/health", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["sidecar"] == "ok"
    assert body["mode"] == "ta2-session"
    assert body["engine"] == "shaped-dev"
    assert body.get("sessionsCapable") is True


def test_health_unreachable(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_ANALYTICS_URL", "http://127.0.0.1:18084")
    from urllib.error import URLError

    with patch(
        "aos_api.routers.analytics.urlrequest.urlopen",
        side_effect=URLError("refused"),
    ):
        r = client.get("/v1/analytics/health", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["sidecar"] == "unreachable"


def test_create_session_503_when_sidecar_down(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_ANALYTICS_URL", "http://127.0.0.1:18084")
    from urllib.error import URLError

    with patch(
        "aos_api.routers.analytics.urlrequest.urlopen",
        side_effect=URLError("refused"),
    ):
        r = client.post(
            "/v1/notebooks/sessions",
            headers=auth_headers,
            json={"purpose": "explore"},
        )
    assert r.status_code == 503
    assert r.json()["code"] == "ANALYTICS_SIDECAR_UNAVAILABLE"


def test_probe_hits_health_path(monkeypatch):
    monkeypatch.setenv("AOS_ANALYTICS_URL", "http://example.invalid:8084")
    seen: list[str] = []

    class _Resp:
        def read(self, _n=None):
            return b'{"status":"ok"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _open(req, timeout=None):  # noqa: ARG001
        seen.append(req.full_url)
        return _Resp()

    with patch("aos_api.routers.analytics.urlrequest.urlopen", side_effect=_open):
        from aos_api.routers.analytics import probe_sidecar

        ok, detail, body = probe_sidecar()
    assert ok is True
    assert detail == "ok"
    assert body.get("status") == "ok"
    assert seen and seen[0].endswith("/health")
