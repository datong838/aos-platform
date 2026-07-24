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


def test_channel_email_with_smtp_ok(client, auth_headers, monkeypatch):
    """192m — AOS_SMTP_HOST set → send 200 (smtplib mocked)."""
    monkeypatch.setenv("AOS_SMTP_HOST", "smtp.test.local")
    monkeypatch.setenv("AOS_SMTP_PORT", "587")
    monkeypatch.setenv("AOS_SMTP_FROM", "aos@test.local")
    monkeypatch.setenv("AOS_SMTP_STARTTLS", "0")

    class _FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def ehlo(self):
            return True

        def starttls(self):
            return True

        def login(self, *a):
            return True

        def send_message(self, msg):
            self.last = msg
            return {}

    monkeypatch.setattr("aos_api.channel_runtime.smtplib.SMTP", _FakeSMTP)
    client.post("/v1/channel-plugins/channel-email/install", headers=auth_headers)
    health = client.get("/v1/channels/channel-email/health", headers=auth_headers)
    assert health.status_code == 200
    assert health.json()["smtpConfigured"] is True
    assert health.json()["mode"] == "smtp"
    send = client.post(
        "/v1/channels/channel-email/send",
        headers=auth_headers,
        json={"to": "user@acme.example", "subject": "hi", "body": "body"},
    )
    assert send.status_code == 200, send.text
    body = send.json()
    assert body["pluginId"] == "channel-email"
    assert body["mode"] == "smtp"
    # SMS still stub
    client.post("/v1/channel-plugins/channel-sms/install", headers=auth_headers)
    sms = client.post(
        "/v1/channels/channel-sms/send",
        headers=auth_headers,
        json={"to": "+100", "body": "hi"},
    )
    assert sms.status_code == 501


def test_198m_channel_sms_with_webhook_ok(client, auth_headers, monkeypatch):
    """198m — AOS_SMS_WEBHOOK_URL set → send 200 (urlopen mocked)."""
    from urllib import request as urlrequest

    monkeypatch.setenv("AOS_SMS_WEBHOOK_URL", "http://sms.test/hook")
    monkeypatch.delenv("AOS_SMS_API_URL", raising=False)
    monkeypatch.delenv("AOS_SMS_API_KEY", raising=False)

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    monkeypatch.setattr(urlrequest, "urlopen", lambda *a, **k: _Resp())
    client.post("/v1/channel-plugins/channel-sms/install", headers=auth_headers)
    health = client.get("/v1/channels/channel-sms/health", headers=auth_headers)
    assert health.status_code == 200
    assert health.json()["smsConfigured"] is True
    assert health.json()["mode"] == "http"
    send = client.post(
        "/v1/channels/channel-sms/send",
        headers=auth_headers,
        json={"to": "+8613800138000", "body": "otp"},
    )
    assert send.status_code == 200, send.text
    body = send.json()
    assert body["pluginId"] == "channel-sms"
    assert body["mode"] == "http"
    assert body["to"] == "+8613800138000"
