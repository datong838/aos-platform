"""TX.4 / T-CROSS — OpenFGA facade (schemes 55/58/61).

Default: local PG tuples. With AOS_OPENFGA_API_URL: HTTP Check/Write/Read.
Frontends must never import OpenFGA SDK (R-ARCH-01).

Scheme 61: production-shaped model (org/project/object/marking) + relation allowlist.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.openfga")

MODEL_VERSION = "aos-prod-v1"

# object read implication (local OR; remote uses computed viewer←editor←owner)
OBJECT_READ_RELATIONS = ("viewer", "editor", "owner")

ALLOWED_RELATIONS = frozenset(
    {
        "viewer",
        "editor",
        "owner",
        "member",
        "parent",
        "bearer",
    }
)

MODEL_CATALOG: dict[str, list[str]] = {
    "user": [],
    "organization": ["member"],
    "project": ["parent", "member"],
    "object": ["owner", "editor", "viewer"],
    "marking": ["bearer"],
}


def object_key(object_type: str, object_id: str) -> str:
    return f"object:{object_type}:{object_id}"


def user_key(subject: str) -> str:
    return f"user:{subject}"


def organization_key(org_id: str) -> str:
    return f"organization:{org_id}"


def project_key(project_id: str) -> str:
    return f"project:{project_id}"


def marking_key(label: str) -> str:
    return f"marking:{label}"


def marking_bearer_enabled() -> bool:
    """Scheme 63: JWT marking OR FGA bearer. Default on; set 0 to JWT-only."""
    raw = (os.getenv("AOS_AUTHZ_MARKING_BEARER") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def user_has_marking_bearer(conn: Any, subject: str, label: str) -> bool:
    """True if user:{subject}#bearer@marking:{label}."""
    if not label:
        return False
    return check(conn, user_key(subject), "bearer", marking_key(label))


def model_payload() -> dict[str, Any]:
    return {
        "modelVersion": MODEL_VERSION,
        "schemaVersion": "1.1",
        "types": [
            {"type": t, "relations": list(rels)}
            for t, rels in MODEL_CATALOG.items()
        ],
        "objectKeyHint": "object:{Type}:{id}",
        "note": "remote computed: viewer←editor←owner; member from parent; local uses OR for object read",
    }


def validate_relation(relation: str) -> None:
    if relation not in ALLOWED_RELATIONS:
        raise ApiError(
            code="AUTHZ_RELATION_UNKNOWN",
            message=f"unknown relation: {relation}",
            status_code=400,
            details={"allowed": sorted(ALLOWED_RELATIONS)},
        )


def openfga_api_url() -> str:
    return (os.getenv("AOS_OPENFGA_API_URL") or "").rstrip("/")


def openfga_store_id() -> str:
    return (os.getenv("AOS_OPENFGA_STORE_ID") or "aos").strip()


def openfga_strict() -> bool:
    return (os.getenv("AOS_OPENFGA_STRICT") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _http_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    base = openfga_api_url()
    if not base:
        raise RuntimeError("AOS_OPENFGA_API_URL not set")
    url = f"{base}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)


def remote_reachable() -> bool:
    if not openfga_api_url():
        return False
    try:
        _http_json("GET", "/healthz", timeout=2.0)
        return True
    except Exception:  # noqa: BLE001
        try:
            # older images may only expose stores list
            _http_json("GET", "/stores", timeout=2.0)
            return True
        except Exception:  # noqa: BLE001
            return False


def status_payload() -> dict[str, Any]:
    url = openfga_api_url()
    mode = "remote" if url else "local"
    reachable = remote_reachable() if url else None
    return {
        "mode": mode,
        "apiUrl": url or None,
        "storeId": openfga_store_id() if url else None,
        "strict": openfga_strict(),
        "reachable": reachable,
        "modelVersion": MODEL_VERSION,
        "types": list(MODEL_CATALOG.keys()),
        "markingBearer": marking_bearer_enabled(),
        "note": (
            "local PG tuples when URL empty; profile openfga for Dev sidecar · "
            "model scheme 61 · marking JWT∪bearer scheme 63"
        ),
    }


def has_tuples_local(conn: Any, obj: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM authz_tuple WHERE object_key=%s LIMIT 1",
        (obj,),
    ).fetchone()
    return bool(row)


def has_tuples_remote(obj: str) -> bool | None:
    """True/False if remote answered; None if unreachable."""
    if not openfga_api_url():
        return None
    store = openfga_store_id()
    try:
        body = _http_json(
            "POST",
            f"/stores/{store}/read",
            {"tuple_key": {"object": obj}},
        )
        tuples = body.get("tuples") or body.get("tuple_keys") or []
        return len(tuples) > 0
    except Exception as exc:  # noqa: BLE001
        log.warning("openfga_remote_read_failed err=%s", type(exc).__name__)
        return None


def has_tuples_for_object(conn: Any, obj: str) -> bool:
    if has_tuples_local(conn, obj):
        return True
    remote = has_tuples_remote(obj)
    if remote is True:
        return True
    return False


def check_local(conn: Any, user: str, relation: str, obj: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM authz_tuple
        WHERE user_key=%s AND relation=%s AND object_key=%s
        LIMIT 1
        """,
        (user, relation, obj),
    ).fetchone()
    return bool(row)


def check_local_object_read(conn: Any, user: str, obj: str) -> bool:
    """Local stand-in for computed viewer←editor←owner."""
    for rel in OBJECT_READ_RELATIONS:
        if check_local(conn, user, rel, obj):
            return True
    return False


def check_remote(user: str, relation: str, obj: str) -> bool | None:
    """Call OpenFGA Check API. Returns None if unreachable / misconfigured."""
    if not openfga_api_url():
        return None
    store_id = openfga_store_id()
    try:
        body = _http_json(
            "POST",
            f"/stores/{store_id}/check",
            {
                "tuple_key": {
                    "user": user,
                    "relation": relation,
                    "object": obj,
                }
            },
        )
        return bool(body.get("allowed"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
        log.warning("openfga_remote_check_failed err=%s", type(exc).__name__)
        return None


def write_tuple_remote(user: str, relation: str, obj: str) -> bool:
    if not openfga_api_url():
        return False
    store = openfga_store_id()
    try:
        _http_json(
            "POST",
            f"/stores/{store}/write",
            {
                "writes": {
                    "tuple_keys": [
                        {"user": user, "relation": relation, "object": obj},
                    ]
                }
            },
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("openfga_remote_write_failed err=%s", type(exc).__name__)
        return False


def check(conn: Any, user: str, relation: str, obj: str) -> bool:
    if openfga_api_url():
        remote = check_remote(user, relation, obj)
        if remote is not None:
            return remote
        if openfga_strict():
            log.warning("openfga_strict_deny user=%s obj=%s", user, obj)
            return False
    if relation == "viewer" and obj.startswith("object:"):
        return check_local_object_read(conn, user, obj)
    return check_local(conn, user, relation, obj)


def write_tuple(conn: Any, user: str, relation: str, obj: str) -> None:
    validate_relation(relation)
    conn.execute(
        """
        INSERT INTO authz_tuple (user_key, relation, object_key)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (user, relation, obj),
    )
    if openfga_api_url():
        ok = write_tuple_remote(user, relation, obj)
        if not ok and openfga_strict():
            raise ApiError(
                code="OPENFGA_WRITE_FAILED",
                message="openfga remote write failed (strict)",
                status_code=502,
            )


def ensure_object_viewer(
    principal: Principal,
    object_type: str,
    object_id: str,
    *,
    conn: Any,
) -> None:
    """If any tuple exists for the object, require viewer (editor/owner imply)."""
    if "admin" in (principal.roles or []):
        return
    obj = object_key(object_type, object_id)
    if not has_tuples_for_object(conn, obj):
        return
    user = user_key(principal.subject)
    if check(conn, user, "viewer", obj):
        return
    log.warning(
        "openfga_forbidden subject=%s object=%s",
        principal.subject,
        obj,
    )
    raise ApiError(
        code="FORBIDDEN",
        message="openfga viewer required",
        status_code=403,
        details={
            "user": user,
            "relation": "viewer",
            "object": obj,
        },
    )
