def test_embed_not_installed(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("AOS_EMBED_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_BASE_URL", raising=False)
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    # KV 可能被其他用例装过：先卸再验
    from aos_api.embedding_registry import uninstall_plugin

    uninstall_plugin("embed-openai-compatible")
    r = client.post(
        "/v1/embeddings/embed-openai-compatible/embed",
        headers=auth_headers,
        json={"texts": ["a"]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "PLUGIN_NOT_INSTALLED"


def test_embed_without_gateway_501(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("AOS_EMBED_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_BASE_URL", raising=False)
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    client.post("/v1/embedding-plugins/embed-openai-compatible/install", headers=auth_headers)
    r = client.post(
        "/v1/embeddings/embed-openai-compatible/embed",
        headers=auth_headers,
        json={"texts": ["hello", "world"]},
    )
    assert r.status_code == 501
    assert r.json()["code"] == "EMBEDDING_STUB"


def test_rerank_cohere_501(client, auth_headers):
    client.post("/v1/embedding-plugins/rerank-cohere/install", headers=auth_headers)
    r = client.post(
        "/v1/embeddings/rerank-cohere/rerank",
        headers=auth_headers,
        json={"query": "q", "documents": ["a", "b"]},
    )
    assert r.status_code == 501
    assert r.json()["code"] == "EMBEDDING_STUB"


def test_unknown_embedding_plugin(client, auth_headers):
    r = client.post(
        "/v1/embeddings/no-such-plugin/embed",
        headers=auth_headers,
        json={"texts": ["x"]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "UNKNOWN_EMBEDDING"


def test_embedding_health(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("AOS_EMBED_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_BASE_URL", raising=False)
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    client.post("/v1/embedding-plugins/embed-openai-compatible/install", headers=auth_headers)
    h = client.get("/v1/embeddings/embed-openai-compatible/health", headers=auth_headers)
    assert h.status_code == 200
    body = h.json()
    assert body["pluginId"] == "embed-openai-compatible"
    assert body["configured"] is False
    assert body["mode"] == "stub"

    client.post("/v1/embedding-plugins/rerank-cohere/install", headers=auth_headers)
    rh = client.get("/v1/embeddings/rerank-cohere/health", headers=auth_headers)
    assert rh.status_code == 200
    assert rh.json()["mode"] == "stub"


def test_embed_live_mocked(client, auth_headers, monkeypatch):
    """有网关配置时走 OpenAI 兼容路径（mock urlopen）。"""
    import json
    from urllib import request as urlrequest

    monkeypatch.setenv("AOS_EMBED_BASE_URL", "http://embed.test")
    monkeypatch.setenv("AOS_EMBED_API_KEY", "sk-test")
    monkeypatch.setenv("AOS_EMBED_MODEL", "text-embedding-3-small")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            payload = {
                "model": "text-embedding-3-small",
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2]},
                    {"index": 1, "embedding": [0.3, 0.4]},
                ],
            }
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(urlrequest, "urlopen", lambda *a, **k: _Resp())
    client.post("/v1/embedding-plugins/embed-openai-compatible/install", headers=auth_headers)
    r = client.post(
        "/v1/embeddings/embed-openai-compatible/embed",
        headers=auth_headers,
        json={"texts": ["a", "b"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pluginId"] == "embed-openai-compatible"
    assert body["vectors"] == [[0.1, 0.2], [0.3, 0.4]]
    assert body["dimensions"] == 2
