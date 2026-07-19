def test_webhook_persisted(client, auth_headers):
    r = client.post(
        "/v1/actions/webhooks",
        headers=auth_headers,
        json={"url": "http://127.0.0.1:9999/hook", "event": "action.approved"},
    )
    assert r.status_code == 200
    wid = r.json()["id"]
    listed = client.get("/v1/actions/webhooks", headers=auth_headers)
    assert listed.status_code == 200
    assert any(i["id"] == wid for i in listed.json()["items"])


def test_channel_webhook_send_dry_run(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_WEBHOOK_DRY_RUN", "1")
    client.post(
        "/v1/actions/webhooks",
        headers=auth_headers,
        json={"url": "http://127.0.0.1:9999/hook", "event": "action.approved"},
    )
    send = client.post(
        "/v1/channels/channel-webhook/send",
        headers=auth_headers,
        json={"event": "action.approved", "ping": True},
    )
    assert send.status_code == 200
    body = send.json()
    assert body["pluginId"] == "channel-webhook"
    assert body.get("matched", 0) >= 1
    assert any(d.get("mode") == "dry-run" for d in body.get("deliveries") or [])


def test_channel_email_without_smtp_501(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_SMTP_HOST", raising=False)
    client.post("/v1/channel-plugins/channel-email/install", headers=auth_headers)
    r = client.post(
        "/v1/channels/channel-email/send",
        headers=auth_headers,
        json={"to": "a@b.com", "subject": "t", "body": "x"},
    )
    assert r.status_code == 501
    assert r.json()["code"] == "CHANNEL_STUB"


def test_channel_sms_501(client, auth_headers):
    client.post("/v1/channel-plugins/channel-sms/install", headers=auth_headers)
    r = client.post(
        "/v1/channels/channel-sms/send",
        headers=auth_headers,
        json={"to": "+100", "body": "hi"},
    )
    assert r.status_code == 501


def test_channel_health(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_SMTP_HOST", raising=False)
    wh = client.get("/v1/channels/channel-webhook/health", headers=auth_headers)
    assert wh.status_code == 200
    assert wh.json()["ok"] is True
    client.post("/v1/channel-plugins/channel-email/install", headers=auth_headers)
    em = client.get("/v1/channels/channel-email/health", headers=auth_headers)
    assert em.status_code == 200
    assert em.json()["smtpConfigured"] is False
