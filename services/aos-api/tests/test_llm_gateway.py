import os

from aos_api.llm_gateway import chat, key_ref, providers_payload


def test_fallback_mock_when_url_unset(monkeypatch):
    monkeypatch.delenv("AOS_LITELLM_URL", raising=False)
    monkeypatch.setenv("AOS_LITELLM_FALLBACK", "mock")
    out = chat("hello-fallback")
    assert out["provider"] == "mock-llm"
    assert out["sidecar"] == "fallback-mock"
    assert out["answer"].endswith("hello-fallback")
    assert key_ref().startswith("vault:")


def test_providers_never_leak_plaintext_key(monkeypatch):
    monkeypatch.delenv("AOS_LITELLM_URL", raising=False)
    payload = providers_payload()
    blob = str(payload)
    assert "aos_dev_litellm_master" not in blob
    assert payload["apiKeyRef"].startswith("vault:")


def test_providers_agnes_when_configured(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "sk-test-only")
    monkeypatch.setenv("AGNES_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("AGNES_TEXT_MODEL", "agnes-2.0-flash")
    monkeypatch.setenv("AGNES_IMAGE_MODEL", "agnes-image-2.1-flash")
    monkeypatch.delenv("AOS_LITELLM_URL", raising=False)
    payload = providers_payload()
    assert payload["sidecar"] == "agnes-openai-compatible"
    assert payload["endpoint"] == "https://example.com/v1"
    assert payload["defaultTextModel"] == "agnes-2.0-flash"
    assert any(i["id"] == "agnes-2.0-flash" for i in payload["items"])
    assert "sk-test-only" not in str(payload)


def test_chat_via_api_fallback(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_LITELLM_URL", raising=False)
    monkeypatch.setenv("AOS_LITELLM_FALLBACK", "mock")
    # re-import path uses env at call time
    r = client.post("/v1/aip/chat", headers=auth_headers, json={"query": "unit"})
    assert r.status_code == 200
    assert r.json()["provider"] in {"mock-llm", "aos-dev"}
    assert "apiKeyRef" in r.json() or r.json().get("sidecar")
