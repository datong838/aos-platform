"""Local vector index (KV) + optional Qdrant — schemes 104/105."""
from __future__ import annotations

import math
import os
import time
import uuid
from typing import Any

from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.vector_index")

MAX_DOCS = 32
DEFAULT_PLUGIN = "embed-openai-compatible"
KV_PREFIX = "vector_index:"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def vector_backend() -> str:
    """local-kv (default) | qdrant — scheme 105."""
    raw = _env("AOS_VECTOR_BACKEND", "local-kv").lower()
    if raw in {"qdrant", "qd"}:
        return "qdrant"
    return "local-kv"


def backend_info() -> dict[str, Any]:
    from aos_api import qdrant_backend as qd

    backend = vector_backend()
    configured = qd.qdrant_configured() if backend == "qdrant" else True
    return {
        "backend": backend,
        "mode": backend if (backend != "qdrant" or configured) else "stub",
        "qdrantConfigured": qd.qdrant_configured(),
        "qdrantUrlSet": bool(qd.qdrant_url()),
    }


def _assert_qdrant_ready() -> None:
    from aos_api import qdrant_backend as qd

    if not qd.qdrant_configured():
        raise ApiError(
            code="VECTOR_BACKEND_STUB",
            message="AOS_VECTOR_BACKEND=qdrant requires AOS_QDRANT_URL",
            status_code=501,
            details={"backend": "qdrant"},
        )


def _kv_key(collection: str) -> str:
    return f"{KV_PREFIX}{(collection or '').strip()}"


def _load(collection: str) -> dict[str, Any]:
    col = (collection or "").strip()
    if not col:
        raise ApiError(code="VALIDATION", message="collection required", status_code=400)
    stored = get_payload(_kv_key(col)) or {}
    items = stored.get("items")
    if not isinstance(items, list):
        items = []
    return {
        "collection": col,
        "pluginId": stored.get("pluginId") or DEFAULT_PLUGIN,
        "model": stored.get("model"),
        "items": [i for i in items if isinstance(i, dict)],
        "updatedAt": stored.get("updatedAt"),
        "mode": "local-kv",
    }


def _save(doc: dict[str, Any]) -> dict[str, Any]:
    col = str(doc["collection"])
    put_payload(
        _kv_key(col),
        {
            "collection": col,
            "pluginId": doc.get("pluginId"),
            "model": doc.get("model"),
            "items": doc.get("items") or [],
            "updatedAt": time.time(),
            "mode": "local-kv",
        },
    )
    return collection_stats(col)


def collection_stats(collection: str) -> dict[str, Any]:
    if vector_backend() == "qdrant":
        _assert_qdrant_ready()
        from aos_api import qdrant_backend as qd

        return qd.collection_stats(collection)
    doc = _load(collection)
    dims = 0
    items = doc["items"]
    if items:
        vec = items[0].get("vector")
        if isinstance(vec, list):
            dims = len(vec)
    return {
        "collection": doc["collection"],
        "pluginId": doc["pluginId"],
        "model": doc.get("model"),
        "total": len(items),
        "dimensions": dims,
        "updatedAt": doc.get("updatedAt"),
        "mode": "local-kv",
    }


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _normalize_documents(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError(code="VALIDATION", message="documents must be a list", status_code=400)
    if len(raw) > MAX_DOCS:
        raise ApiError(
            code="VALIDATION",
            message=f"documents exceeds max {MAX_DOCS}",
            status_code=400,
            details={"max": MAX_DOCS, "got": len(raw)},
        )
    out: list[dict[str, Any]] = []
    for i, row in enumerate(raw):
        if isinstance(row, str):
            text = row
            did = f"doc-{i}"
            meta: dict[str, Any] = {}
        elif isinstance(row, dict):
            text = str(row.get("text") or row.get("content") or "").strip()
            did = str(row.get("id") or f"doc-{i}")
            meta = dict(row.get("meta") or {}) if isinstance(row.get("meta"), dict) else {}
        else:
            raise ApiError(code="VALIDATION", message=f"documents[{i}] invalid", status_code=400)
        if not text:
            raise ApiError(code="VALIDATION", message=f"documents[{i}].text required", status_code=400)
        out.append({"id": did, "text": text, "meta": meta})
    return out


def _sample_workorder_docs(limit: int = 8) -> list[dict[str, Any]]:
    """Best-effort sample from PG ObjectSet; fallback mock."""
    items: list[dict[str, Any]] = []
    try:
        from aos_api.db import connect

        with connect() as conn:
            rows = conn.execute(
                """
                SELECT object_id, props FROM obj_instance
                WHERE object_type=%s ORDER BY object_id LIMIT %s
                """,
                ("WorkOrder", limit),
            ).fetchall()
        for r in rows:
            props = r["props"] if isinstance(r["props"], dict) else {}
            items.append({"id": r["object_id"], **props})
    except Exception as exc:  # noqa: BLE001
        log.debug("vector_index_sample_pg_skip err=%s", exc)
        try:
            from aos_api import mock_data

            blob = mock_data.query_objects(filters=[], page=1, page_size=limit)
            items = list(blob.get("items") or []) if isinstance(blob, dict) else []
        except Exception as exc2:  # noqa: BLE001
            log.debug("vector_index_sample_mock_skip err=%s", exc2)
            return []

    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or it.get("name") or it.get("id") or "").strip()
        oid = str(it.get("id") or title or uuid.uuid4().hex[:8])
        if title:
            out.append(
                {
                    "id": oid,
                    "text": title,
                    "meta": {"source": "object-set", "objectType": "WorkOrder"},
                }
            )
    return out

def upsert(
    *,
    collection: str,
    documents: list[dict[str, Any]] | None = None,
    plugin_id: str = DEFAULT_PLUGIN,
    replace: bool = False,
    pipeline_id: str | None = None,
    auto_sample: bool = False,
) -> dict[str, Any]:
    from aos_api.embedding_runtime import dispatch_embed

    docs = list(documents or [])
    if not docs and auto_sample:
        docs = _sample_workorder_docs()
    if not docs:
        raise ApiError(
            code="VALIDATION",
            message="documents required (or enable autoSample with WorkOrder rows)",
            status_code=400,
        )
    if len(docs) > MAX_DOCS:
        raise ApiError(code="VALIDATION", message=f"documents exceeds max {MAX_DOCS}", status_code=400)

    use_qdrant = vector_backend() == "qdrant"
    if use_qdrant:
        _assert_qdrant_ready()

    texts = [d["text"] for d in docs]
    emb = dispatch_embed(plugin_id, {"texts": texts})
    vectors = emb.get("vectors") or []
    if len(vectors) != len(docs):
        raise ApiError(code="EMBEDDING_UPSTREAM", message="vector count mismatch", status_code=502)

    rows: list[dict[str, Any]] = []
    for d, vec in zip(docs, vectors):
        rows.append(
            {
                "id": d["id"],
                "text": d["text"],
                "vector": vec,
                "meta": {**(d.get("meta") or {}), **({"pipelineId": pipeline_id} if pipeline_id else {})},
            }
        )

    if use_qdrant:
        from aos_api import qdrant_backend as qd

        stats = qd.upsert_points(
            collection=collection,
            rows=rows,
            plugin_id=plugin_id,
            replace=replace,
        )
        log.info(
            "vector_upsert_qdrant collection=%s n=%s total=%s plugin=%s",
            collection,
            len(docs),
            stats.get("total"),
            plugin_id,
        )
        return {
            **stats,
            "upserted": len(docs),
            "pluginId": plugin_id,
            "model": emb.get("model"),
            "sidecar": emb.get("sidecar"),
            "pipelineId": pipeline_id,
            "mode": "qdrant",
        }

    store = _load(collection)
    existing = [] if replace else list(store["items"])
    by_id = {str(x.get("id")): x for x in existing if x.get("id")}
    for row in rows:
        by_id[row["id"]] = row
    items = list(by_id.values())
    store["items"] = items
    store["pluginId"] = plugin_id
    store["model"] = emb.get("model")
    stats = _save(store)
    log.info(
        "vector_upsert collection=%s n=%s total=%s plugin=%s",
        collection,
        len(docs),
        stats["total"],
        plugin_id,
    )
    return {
        **stats,
        "upserted": len(docs),
        "pluginId": plugin_id,
        "model": emb.get("model"),
        "sidecar": emb.get("sidecar"),
        "pipelineId": pipeline_id,
    }


def search(
    *,
    collection: str,
    query: str,
    plugin_id: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    from aos_api.embedding_runtime import dispatch_embed

    q = (query or "").strip()
    if not q:
        raise ApiError(code="VALIDATION", message="query required", status_code=400)

    if vector_backend() == "qdrant":
        _assert_qdrant_ready()
        from aos_api import qdrant_backend as qd

        pid = (plugin_id or DEFAULT_PLUGIN).strip()
        emb = dispatch_embed(pid, {"texts": [q]})
        qvec = (emb.get("vectors") or [[]])[0]
        if not isinstance(qvec, list) or not qvec:
            raise ApiError(code="EMBEDDING_UPSTREAM", message="empty query vector", status_code=502)
        out = qd.search_points(collection=collection, vector=qvec, top_k=top_k)
        return {
            **out,
            "pluginId": pid,
            "model": emb.get("model"),
        }

    store = _load(collection)
    if not store["items"]:
        return {"collection": collection, "results": [], "totalIndexed": 0, "mode": "local-kv"}
    pid = (plugin_id or store.get("pluginId") or DEFAULT_PLUGIN).strip()
    emb = dispatch_embed(pid, {"texts": [q]})
    qvec = (emb.get("vectors") or [[]])[0]
    if not isinstance(qvec, list) or not qvec:
        raise ApiError(code="EMBEDDING_UPSTREAM", message="empty query vector", status_code=502)
    scored: list[dict[str, Any]] = []
    for row in store["items"]:
        vec = row.get("vector")
        if not isinstance(vec, list):
            continue
        scored.append(
            {
                "id": row.get("id"),
                "text": row.get("text"),
                "score": round(_cosine([float(x) for x in qvec], [float(x) for x in vec]), 6),
                "meta": row.get("meta") or {},
            }
        )
    scored.sort(key=lambda r: float(r.get("score") or 0), reverse=True)
    k = max(1, min(int(top_k or 5), 32))
    return {
        "collection": collection,
        "pluginId": pid,
        "model": emb.get("model"),
        "totalIndexed": len(store["items"]),
        "results": scored[:k],
        "mode": "local-kv",
    }


def embed_pipeline(
    pipeline_id: str,
    payload: dict[str, Any] | None,
    *,
    pipelines: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pid = (pipeline_id or "").strip()
    if pid not in pipelines:
        raise ApiError(code="NOT_FOUND", message=f"pipeline not found: {pid}", status_code=404)
    body = payload or {}
    plugin_id = str(body.get("pluginId") or DEFAULT_PLUGIN).strip()
    collection = str(body.get("collection") or pid).strip()
    docs = _normalize_documents(body.get("documents"))
    replace = bool(body.get("replace", False))
    auto = bool(body.get("autoSample", not docs))
    out = upsert(
        collection=collection,
        documents=docs or None,
        plugin_id=plugin_id,
        replace=replace,
        pipeline_id=pid,
        auto_sample=auto and not docs,
    )
    pipe = pipelines[pid]
    last = dict(pipe.get("lastBuild") or {})
    tasks = list(last.get("tasks") or [])
    tasks = [t for t in tasks if not (isinstance(t, dict) and t.get("name") == "embed")]
    tasks.append({"name": "embed", "ok": True, "collection": collection, "upserted": out.get("upserted")})
    last["tasks"] = tasks
    pipe["lastBuild"] = last
    pipe["vectorCollection"] = collection
    return out
