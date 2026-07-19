"""Qdrant REST adapter for vector index — scheme 105."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from typing import Any

from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.qdrant_backend")

_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def qdrant_url() -> str:
    return _env("AOS_QDRANT_URL").rstrip("/")


def qdrant_api_key() -> str:
    return _env("AOS_QDRANT_API_KEY")


def qdrant_configured() -> bool:
    return bool(qdrant_url())


def sanitize_collection(name: str) -> str:
    raw = (name or "").strip() or "default"
    cleaned = _SAFE.sub("_", raw).strip("_") or "default"
    if not cleaned.startswith("aos_"):
        cleaned = f"aos_{cleaned}"
    return cleaned[:255]


def point_uuid(collection: str, doc_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{collection}:{doc_id}"))


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    key = qdrant_api_key()
    if key:
        h["api-key"] = key
    return h


def _request(method: str, path: str, payload: dict[str, Any] | None = None, *, timeout: float = 30) -> Any:
    base = qdrant_url()
    if not base:
        raise ApiError(
            code="VECTOR_BACKEND_STUB",
            message="AOS_VECTOR_BACKEND=qdrant requires AOS_QDRANT_URL",
            status_code=501,
        )
    url = f"{base}{path}"
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code == 404:
            raise FileNotFoundError(detail) from None
        raise ApiError(
            code="QDRANT_UPSTREAM",
            message=f"qdrant HTTP {exc.code}",
            status_code=502,
            details={"status": exc.code, "body": detail, "path": path},
        ) from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        raise ApiError(
            code="QDRANT_UPSTREAM",
            message=f"qdrant request failed: {exc}",
            status_code=502,
            details={"path": path},
        ) from None


def ensure_collection(collection: str, dim: int) -> str:
    name = sanitize_collection(collection)
    try:
        _request("GET", f"/collections/{name}")
        return name
    except FileNotFoundError:
        pass
    except ApiError:
        pass
    body = {"vectors": {"size": int(dim), "distance": "Cosine"}}
    try:
        _request("PUT", f"/collections/{name}", body)
    except ApiError as exc:
        try:
            _request("GET", f"/collections/{name}")
            return name
        except Exception:
            raise exc from None
    log.info("qdrant_collection_ensured name=%s dim=%s", name, dim)
    return name


def upsert_points(
    *,
    collection: str,
    rows: list[dict[str, Any]],
    plugin_id: str,
    replace: bool = False,
) -> dict[str, Any]:
    if not rows:
        raise ApiError(code="VALIDATION", message="no points to upsert", status_code=400)
    dim = len(rows[0]["vector"])
    name = ensure_collection(collection, dim)
    if replace:
        try:
            _request("DELETE", f"/collections/{name}")
        except (ApiError, FileNotFoundError):
            pass
        name = ensure_collection(collection, dim)

    points = []
    for row in rows:
        points.append(
            {
                "id": point_uuid(name, str(row["id"])),
                "vector": [float(x) for x in row["vector"]],
                "payload": {
                    "id": row["id"],
                    "text": row["text"],
                    "meta": row.get("meta") or {},
                    "pluginId": plugin_id,
                },
            }
        )
    _request("PUT", f"/collections/{name}/points?wait=true", {"points": points})
    stats = collection_stats(collection)
    return {**stats, "upserted": len(points), "qdrantCollection": name}


def search_points(
    *,
    collection: str,
    vector: list[float],
    top_k: int = 5,
) -> dict[str, Any]:
    name = sanitize_collection(collection)
    try:
        body = _request(
            "POST",
            f"/collections/{name}/points/search",
            {
                "vector": [float(x) for x in vector],
                "limit": max(1, min(int(top_k or 5), 32)),
                "with_payload": True,
            },
        )
    except FileNotFoundError:
        return {
            "collection": collection,
            "results": [],
            "totalIndexed": 0,
            "mode": "qdrant",
            "qdrantCollection": name,
        }
    raw = body.get("result") if isinstance(body, dict) else None
    if not isinstance(raw, list):
        raw = []
    results: list[dict[str, Any]] = []
    for hit in raw:
        if not isinstance(hit, dict):
            continue
        payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
        results.append(
            {
                "id": payload.get("id") or hit.get("id"),
                "text": payload.get("text"),
                "score": round(float(hit.get("score") or 0), 6),
                "meta": payload.get("meta") or {},
            }
        )
    total = 0
    try:
        total = int(collection_stats(collection).get("total") or 0)
    except ApiError:
        total = len(results)
    return {
        "collection": collection,
        "results": results,
        "totalIndexed": total,
        "mode": "qdrant",
        "qdrantCollection": name,
    }


def collection_stats(collection: str) -> dict[str, Any]:
    name = sanitize_collection(collection)
    try:
        body = _request("GET", f"/collections/{name}")
    except FileNotFoundError:
        return {
            "collection": collection,
            "total": 0,
            "dimensions": 0,
            "mode": "qdrant",
            "qdrantCollection": name,
        }
    result = body.get("result") if isinstance(body, dict) else {}
    result = result if isinstance(result, dict) else {}
    points = result.get("points_count")
    if points is None:
        points = result.get("indexed_vectors_count") or 0
    cfg = result.get("config") if isinstance(result.get("config"), dict) else {}
    params = cfg.get("params") if isinstance(cfg.get("params"), dict) else {}
    vectors = params.get("vectors") if isinstance(params.get("vectors"), dict) else {}
    dim = int(vectors.get("size") or 0)
    return {
        "collection": collection,
        "total": int(points or 0),
        "dimensions": dim,
        "mode": "qdrant",
        "qdrantCollection": name,
    }
