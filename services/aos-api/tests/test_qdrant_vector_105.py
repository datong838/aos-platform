"""105 · Qdrant optional vector backend unit tests."""
from __future__ import annotations

import json
from urllib import request as urlrequest


def _mock_embed_and_qdrant(monkeypatch, *, search_hits: list[dict] | None = None):
    """Route urlopen: embed.test → embeddings; qdrant.test → Qdrant REST."""
    monkeypatch.setenv("AOS_VECTOR_BACKEND", "qdrant")
    monkeypatch.setenv("AOS_QDRANT_URL", "http://qdrant.test")
    monkeypatch.setenv("AOS_EMBED_BASE_URL", "http://embed.test")
    monkeypatch.setenv("AOS_EMBED_API_KEY", "sk-test")
    monkeypatch.setenv("AOS_EMBED_MODEL", "text-embedding-3-small")

    state = {"points": [], "dim": 2, "deleted": False}

    def _urlopen(req, timeout=60):  # noqa: ARG001
        url = getattr(req, "full_url", None) or req.get_full_url()
        method = (req.get_method() or "GET").upper()
        raw = req.data.decode("utf-8") if req.data else ""
        body = json.loads(raw) if raw else {}

        class _Resp:
            def __init__(self, payload, status=200):
                self._payload = payload
                self.status = status

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(self._payload).encode("utf-8")

        # --- OpenAI embed ---
        if "embed.test" in url and "/embeddings" in url:
            texts = body.get("input") or []
            n = len(texts)
            if n == 1:
                vecs = [[1.0, 0.0]]
            else:
                vecs = [[1.0, 0.0], [0.0, 1.0]] + [[0.1, 0.1]] * max(0, n - 2)
                vecs = vecs[:n]
            return _Resp(
                {
                    "model": "text-embedding-3-small",
                    "data": [{"index": i, "embedding": vecs[i]} for i in range(n)],
                }
            )

        # --- Qdrant ---
        if "qdrant.test" in url:
            if method == "GET" and "/collections/" in url:
                name = url.rstrip("/").split("/")[-1]
                if state["deleted"] or not state["points"]:
                    # first ensure may 404
                    if not state.get("ensured"):
                        err = urlrequest.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
                        raise err
                return _Resp(
                    {
                        "result": {
                            "points_count": len(state["points"]),
                            "config": {"params": {"vectors": {"size": state["dim"]}}},
                        }
                    }
                )
            if method == "PUT" and "/collections/" in url and "/points" not in url:
                state["ensured"] = True
                state["deleted"] = False
                state["dim"] = int((body.get("vectors") or {}).get("size") or 2)
                return _Resp({"result": True})
            if method == "DELETE" and "/collections/" in url:
                state["points"] = []
                state["deleted"] = True
                state["ensured"] = False
                return _Resp({"result": True})
            if method == "PUT" and "/points" in url:
                state["ensured"] = True
                state["deleted"] = False
                for p in body.get("points") or []:
                    state["points"].append(p)
                return _Resp({"result": {"status": "ok"}})
            if method == "POST" and "/points/search" in url:
                hits = search_hits
                if hits is None:
                    hits = [
                        {
                            "id": "uuid-a",
                            "score": 0.99,
                            "payload": {"id": "a", "text": "机房巡检", "meta": {}},
                        }
                    ]
                return _Resp({"result": hits})
            return _Resp({"result": True})

        raise AssertionError(f"unexpected urlopen: {method} {url}")

    # HTTPError needs a file-like for read in some paths — patch raise with proper fp
    import io

    real_http_error = urlrequest.HTTPError

    class _HTTPError(real_http_error):
        def __init__(self, url, code, msg, hdrs, fp):
            if fp is None:
                fp = io.BytesIO(b"{}")
            super().__init__(url, code, msg, hdrs, fp)

    monkeypatch.setattr(urlrequest, "HTTPError", _HTTPError)
    monkeypatch.setattr(urlrequest, "urlopen", _urlopen)
    return state


def test_backend_default_local_kv(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_VECTOR_BACKEND", raising=False)
    monkeypatch.delenv("AOS_QDRANT_URL", raising=False)
    r = client.get("/v1/aip/vector-index/_backend", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "local-kv"
    assert body["mode"] == "local-kv"


def test_qdrant_without_url_501(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_VECTOR_BACKEND", "qdrant")
    monkeypatch.delenv("AOS_QDRANT_URL", raising=False)
    monkeypatch.setenv("AOS_EMBED_BASE_URL", "http://embed.test")
    monkeypatch.setenv("AOS_EMBED_API_KEY", "sk-test")
    client.post("/v1/embedding-plugins/embed-openai-compatible/install", headers=auth_headers)

    # embed still needs mock if it got past backend check — but should fail at backend first
    # Actually order: embed first then qdrant ready. So need mock embed OR backend check before embed.
    # vector_index upsert: embed first, then _assert_qdrant_ready. So embed runs first!
    # Fix: assert qdrant ready BEFORE embed when backend is qdrant — better UX and saves embed call.
    r = client.post(
        "/v1/aip/vector-index/upsert",
        headers=auth_headers,
        json={"collection": "c1", "documents": [{"id": "1", "text": "x"}]},
    )
    # If embed runs first without mock → 502 or network. Reorder in vector_index.
    assert r.status_code == 501, r.text
    assert r.json()["code"] == "VECTOR_BACKEND_STUB"


def test_qdrant_upsert_and_search(client, auth_headers, monkeypatch):
    _mock_embed_and_qdrant(monkeypatch)
    client.post("/v1/embedding-plugins/embed-openai-compatible/install", headers=auth_headers)

    up = client.post(
        "/v1/aip/vector-index/upsert",
        headers=auth_headers,
        json={
            "collection": "demo-pipe-wo",
            "replace": True,
            "documents": [
                {"id": "a", "text": "机房巡检"},
                {"id": "b", "text": "备件更换"},
            ],
        },
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["mode"] == "qdrant"
    assert body["upserted"] == 2

    meta = client.get("/v1/aip/vector-index/_backend", headers=auth_headers)
    assert meta.json()["backend"] == "qdrant"
    assert meta.json()["qdrantConfigured"] is True

    search = client.post(
        "/v1/aip/vector-index/search",
        headers=auth_headers,
        json={"collection": "demo-pipe-wo", "query": "巡检", "topK": 2},
    )
    assert search.status_code == 200, search.text
    assert search.json()["mode"] == "qdrant"
    assert search.json()["results"][0]["id"] == "a"


def test_sanitize_collection_unit():
    from aos_api.qdrant_backend import sanitize_collection, point_uuid

    assert sanitize_collection("demo-pipe-wo") == "aos_demo-pipe-wo"
    assert sanitize_collection("aos_x") == "aos_x"
    u1 = point_uuid("aos_c", "a")
    u2 = point_uuid("aos_c", "a")
    assert u1 == u2
