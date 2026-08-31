import pytest

from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers.wave_ext import put_llm_provider_plugin_config


def test_provider_config_requires_admin_role():
    principal = Principal(
        subject="user:viewer",
        org_id="dev-org",
        project_id="dev-project",
        roles=["viewer"],
    )
    with pytest.raises(ApiError) as exc_info:
        put_llm_provider_plugin_config(
            "agnes-text",
            {"secretRef": "keychain://aos/test-provider-ref"},
            principal,
        )
    assert exc_info.value.code == "FORBIDDEN"


def test_llm_provider_plugins_catalog_and_install(client, auth_headers):
    g = client.get("/v1/aip/llm-provider-plugins", headers=auth_headers)
    assert g.status_code == 200
    body = g.json()
    assert body["totals"]["all"] >= 30
    ids = {i["id"] for i in body["items"]}
    assert "deepseek" in ids
    assert "openai" in ids
    assert "kling-video" in ids

    inst = client.post("/v1/aip/llm-provider-plugins/deepseek/install", headers=auth_headers)
    assert inst.status_code == 200
    assert inst.json()["installed"] is True
    g2 = client.get("/v1/aip/llm-provider-plugins", headers=auth_headers)
    deep = next(i for i in g2.json()["items"] if i["id"] == "deepseek")
    assert deep["installed"] is True

    pub = client.put(
        "/v1/aip/llm-provider-plugins/custom",
        headers=auth_headers,
        json={
            "id": "corp-test-llm",
            "name": "Corp Test",
            "nameZh": "企业测试模型",
            "tier": "mid",
            "modalities": ["text"],
            "formFamily": "openai_compatible",
        },
    )
    assert pub.status_code == 200
    assert pub.json()["item"]["id"] == "corp-test-llm"

    plugins = client.get("/v1/plugins", headers=auth_headers)
    assert plugins.status_code == 200
    kinds = {i.get("kind") for i in plugins.json()["items"]}
    assert "llm-provider" in kinds


def test_provider_config_accepts_only_versioned_opaque_secret_ref(client, auth_headers):
    listed = client.get("/v1/aip/llm-provider-plugins", headers=auth_headers).json()
    plugin = next(item for item in listed["items"] if item["id"] == "agnes-text")
    version = int((plugin.get("config") or {}).get("revision") or 0)
    saved = client.put(
        "/v1/aip/llm-provider-plugins/agnes-text/config",
        headers=auth_headers,
        json={
            "displayName": "Agnes Text",
            "baseUrl": "https://api.agnes-ai.cn/v1",
            "secretRef": "keychain://aos/test-provider-ref",
            "models": ["agnes-2.5-flash"],
            "ready": bool(plugin.get("ready")),
            "expectedVersion": version,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["config"]["revision"] == version + 1
    assert saved.json()["config"]["secretRef"] == "keychain://aos/test-provider-ref"

    stale = client.put(
        "/v1/aip/llm-provider-plugins/agnes-text/config",
        headers=auth_headers,
        json={"secretRef": "keychain://aos/stale", "expectedVersion": version},
    )
    assert stale.status_code == 409

    invalid = client.put(
        "/v1/aip/llm-provider-plugins/agnes-text/config",
        headers=auth_headers,
        json={"secretRef": "plaintext-secret", "expectedVersion": version + 1},
    )
    assert invalid.status_code == 400

    plaintext = client.put(
        "/v1/aip/llm-provider-plugins/agnes-text/config",
        headers=auth_headers,
        json={"apiKey": "must-not-enter-config", "expectedVersion": version + 1},
    )
    assert plaintext.status_code == 400
    assert plaintext.json()["code"] == "PLAINTEXT_SECRET_REJECTED"

    revoked = client.put(
        "/v1/aip/llm-provider-plugins/agnes-text/config",
        headers=auth_headers,
        json={
            "secretRef": "",
            "ready": False,
            "expectedVersion": version + 1,
        },
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["config"]["revision"] == version + 2
    assert revoked.json()["config"]["secretRef"] == ""
    assert revoked.json()["ready"] is False
