"""109 · TA.0 analytics / notebooks contract stubs."""


def test_analytics_health_unset(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_ANALYTICS_URL", raising=False)
    r = client.get("/v1/analytics/health", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["sidecar"] == "unset"
    assert body["notebookUi"] == "notebook7"
    assert body["status"] == "degraded"
    assert body["mode"] == "ta0-contract"


def test_create_notebook_session_503_without_sidecar(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_ANALYTICS_URL", raising=False)
    r = client.post(
        "/v1/notebooks/sessions",
        headers=auth_headers,
        json={"objectType": "WorkOrder", "purpose": "explore"},
    )
    assert r.status_code == 503
    assert r.json()["code"] == "ANALYTICS_SIDECAR_UNAVAILABLE"


def test_list_notebook_sessions_empty_ok(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_ANALYTICS_URL", raising=False)
    r = client.get("/v1/notebooks/sessions", headers=auth_headers)
    assert r.status_code == 200
    assert "items" in r.json()


def test_sql_preview_select_1_ok(client, auth_headers):
    """TA.4 · select 1 is live (no longer 501 stub)."""
    r = client.post(
        "/v1/analytics/sql/preview",
        headers=auth_headers,
        json={"sql": "select 1", "limit": 10},
    )
    assert r.status_code == 200
    assert r.json()["rows"] == [{"v": 1}]


def test_sql_preview_requires_sql(client, auth_headers):
    r = client.post(
        "/v1/analytics/sql/preview",
        headers=auth_headers,
        json={"sql": "  ", "limit": 10},
    )
    assert r.status_code == 400


def test_get_session_404(client, auth_headers):
    r = client.get("/v1/notebooks/sessions/no-such", headers=auth_headers)
    assert r.status_code == 404


def test_stop_seeded_session(client, auth_headers):
    from aos_api.routers.analytics import seed_demo_session_meta_for_tests

    row = seed_demo_session_meta_for_tests()
    sid = row["id"]
    g = client.get(f"/v1/notebooks/sessions/{sid}", headers=auth_headers)
    assert g.status_code == 200
    d = client.delete(f"/v1/notebooks/sessions/{sid}", headers=auth_headers)
    assert d.status_code == 200
    assert d.json()["status"] == "stopped"
