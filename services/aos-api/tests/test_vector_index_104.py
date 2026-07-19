def _mock_embed(monkeypatch, vectors_by_n: dict[int, list[list[float]]] | None = None):
    import json
    from urllib import request as urlrequest

    monkeypatch.delenv("AOS_VECTOR_BACKEND", raising=False)
    monkeypatch.delenv("AOS_QDRANT_URL", raising=False)
    monkeypatch.setenv("AOS_EMBED_BASE_URL", "http://embed.test")
    monkeypatch.setenv("AOS_EMBED_API_KEY", "sk-test")
    monkeypatch.setenv("AOS_EMBED_MODEL", "text-embedding-3-small")

    def _urlopen(req, timeout=60):  # noqa: ARG001
        body = json.loads(req.data.decode("utf-8"))
        texts = body.get("input") or []
        n = len(texts)
        preset = (vectors_by_n or {}).get(n)
        if preset is None:
            preset = [[float(i + 1), 0.1] for i in range(n)]

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(
                    {
                        "model": "text-embedding-3-small",
                        "data": [{"index": i, "embedding": preset[i]} for i in range(n)],
                    }
                ).encode("utf-8")

        return _Resp()

    monkeypatch.setattr(urlrequest, "urlopen", _urlopen)


def test_pipeline_embed_unknown_404(client, auth_headers):
    r = client.post(
        "/v1/pipelines/no-such-pipe/embed",
        headers=auth_headers,
        json={"documents": [{"text": "a"}]},
    )
    assert r.status_code == 404


def test_pipeline_embed_no_gateway_501(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_VECTOR_BACKEND", raising=False)
    monkeypatch.delenv("AOS_QDRANT_URL", raising=False)
    monkeypatch.delenv("AOS_EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("AOS_EMBED_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_BASE_URL", raising=False)
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    client.post("/v1/embedding-plugins/embed-openai-compatible/install", headers=auth_headers)
    # ensure demo pipeline exists
    client.get("/v1/pipelines", headers=auth_headers)
    from aos_api.routers import wave_ext

    wave_ext.ensure_demo_data_seed()
    r = client.post(
        "/v1/pipelines/demo-pipe-wo/embed",
        headers=auth_headers,
        json={
            "collection": "probe-501-empty",
            "documents": [{"id": "d1", "text": "hello"}],
        },
    )
    assert r.status_code == 501
    assert r.json()["code"] == "EMBEDDING_STUB"
    stats = client.get("/v1/aip/vector-index/probe-501-empty", headers=auth_headers)
    assert stats.status_code == 200
    assert stats.json()["total"] == 0


def test_pipeline_embed_and_search(client, auth_headers, monkeypatch):
    _mock_embed(
        monkeypatch,
        {
            2: [[1.0, 0.0], [0.0, 1.0]],
            1: [[1.0, 0.0]],  # query ~ first doc
        },
    )
    client.post("/v1/embedding-plugins/embed-openai-compatible/install", headers=auth_headers)
    from aos_api.routers import wave_ext

    wave_ext.ensure_demo_data_seed()
    up = client.post(
        "/v1/pipelines/demo-pipe-wo/embed",
        headers=auth_headers,
        json={
            "replace": True,
            "documents": [
                {"id": "a", "text": "机房巡检"},
                {"id": "b", "text": "备件更换"},
            ],
        },
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["upserted"] == 2
    assert body["total"] == 2
    assert body["mode"] == "local-kv"

    search = client.post(
        "/v1/aip/vector-index/search",
        headers=auth_headers,
        json={"collection": "demo-pipe-wo", "query": "巡检", "topK": 2},
    )
    assert search.status_code == 200
    results = search.json()["results"]
    assert results
    assert results[0]["id"] == "a"


def test_upsert_too_many_docs(client, auth_headers, monkeypatch):
    _mock_embed(monkeypatch)
    client.post("/v1/embedding-plugins/embed-openai-compatible/install", headers=auth_headers)
    docs = [{"id": f"d{i}", "text": f"t{i}"} for i in range(33)]
    r = client.post(
        "/v1/aip/vector-index/upsert",
        headers=auth_headers,
        json={"collection": "c-overflow", "documents": docs},
    )
    assert r.status_code == 400
