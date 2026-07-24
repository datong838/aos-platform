"""TX.4 — Marking engine: object/field + inheritance (scheme 52/55)."""
from __future__ import annotations

from typing import Any

from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.marking")

INHERIT_REL = "inherits_markings_from"


def _as_marking_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    return []


def ensure_markings(
    principal: Principal,
    required: list[str] | None,
    *,
    conn: Any | None = None,
) -> None:
    """Require principal.markings ⊇ required (unless admin).

    Scheme 63: missing labels may be satisfied by OpenFGA marking#bearer when
    conn is provided and AOS_AUTHZ_MARKING_BEARER is enabled (default on).
    """
    req = [r for r in (required or []) if r]
    if not req:
        return
    if "admin" in (principal.roles or []):
        return
    allowed = set(principal.markings or [])
    missing = [r for r in req if r not in allowed]
    if missing and conn is not None:
        from aos_api.openfga import marking_bearer_enabled, user_has_marking_bearer

        if marking_bearer_enabled():
            still: list[str] = []
            for label in missing:
                if user_has_marking_bearer(conn, principal.subject, label):
                    log.info(
                        "marking_via_fga_bearer subject=%s label=%s",
                        principal.subject,
                        label,
                    )
                else:
                    still.append(label)
            missing = still
    if missing:
        log.warning(
            "marking_forbidden subject=%s missing=%s",
            principal.subject,
            missing,
        )
        raise ApiError(
            code="FORBIDDEN",
            message="marking insufficient",
            status_code=403,
            details={"required": req, "missing": missing, "have": sorted(allowed)},
        )


def field_marking_map(properties: list[dict[str, Any]] | None) -> dict[str, list[str]]:
    """property name → requiredMarkings (only fields that declare them)."""
    out: dict[str, list[str]] = {}
    for p in properties or []:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or p.get("id")
        if not name:
            continue
        req = p.get("requiredMarkings") or p.get("markings") or []
        if isinstance(req, str):
            req = [req]
        req = [r for r in req if r]
        if req:
            out[str(name)] = list(req)
    return out


def can_see_field(
    principal: Principal,
    required: list[str],
    *,
    conn: Any | None = None,
) -> bool:
    """True if JWT markings ∪ optional FGA marking#bearer cover required (scheme 65)."""
    if not required:
        return True
    if "admin" in (principal.roles or []):
        return True
    allowed = set(principal.markings or [])
    if all(r in allowed for r in required):
        return True
    if conn is None:
        return False
    from aos_api.openfga import marking_bearer_enabled, user_has_marking_bearer

    if not marking_bearer_enabled():
        return False
    for label in required:
        if label in allowed:
            continue
        if not user_has_marking_bearer(conn, principal.subject, label):
            return False
    return True


def redact_props(
    principal: Principal,
    props: dict[str, Any] | None,
    properties: list[dict[str, Any]] | None,
    *,
    conn: Any | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Drop fields the principal cannot see. Returns (visible_props, redacted_field_names)."""
    src = dict(props or {})
    fmap = field_marking_map(properties)
    if not fmap:
        return src, []
    redacted: list[str] = []
    for field, req in fmap.items():
        if field not in src:
            continue
        if not can_see_field(principal, req, conn=conn):
            src.pop(field, None)
            redacted.append(field)
    if redacted:
        log.info(
            "field_redact subject=%s fields=%s",
            principal.subject,
            redacted,
        )
    return src, redacted


def apply_field_redaction(
    principal: Principal,
    payload: dict[str, Any],
    properties: list[dict[str, Any]] | None,
    *,
    reserved: set[str] | None = None,
    conn: Any | None = None,
) -> dict[str, Any]:
    """Redact object payload in place-style copy; attach _redactedFields when any."""
    skip = reserved or {"id", "type", "_redactedFields"}
    meta = {k: payload[k] for k in skip if k in payload}
    body = {k: v for k, v in payload.items() if k not in skip}
    visible, redacted = redact_props(principal, body, properties, conn=conn)
    out = {**meta, **visible}
    if redacted:
        out["_redactedFields"] = sorted(redacted)
    return out


def ensure_field_writes(
    principal: Principal,
    proposed: dict[str, Any] | None,
    properties: list[dict[str, Any]] | None,
    *,
    conn: Any | None = None,
) -> None:
    """Forbid writing fields whose requiredMarkings the principal lacks."""
    fmap = field_marking_map(properties)
    if not fmap or not proposed:
        return
    for field, req in fmap.items():
        if field in proposed:
            ensure_markings(principal, req, conn=conn)


def type_required_markings(conn: Any, object_type: str) -> list[str]:
    try:
        row = conn.execute(
            "SELECT required_markings FROM meta_object_type WHERE id=%s",
            (object_type,),
        ).fetchone()
    except Exception:  # noqa: BLE001 — column may be absent on old DBs mid-migrate
        return []
    if not row:
        return []
    return _as_marking_list(row.get("required_markings"))


def instance_required_markings(props: dict[str, Any] | None) -> list[str]:
    return _as_marking_list((props or {}).get("_requiredMarkings"))


def effective_markings(
    conn: Any,
    object_type: str,
    object_id: str,
) -> list[str]:
    """Type ∪ instance ∪ 1-hop parent (inherits_markings_from) markings."""
    out: set[str] = set(type_required_markings(conn, object_type))
    row = conn.execute(
        "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
        (object_type, object_id),
    ).fetchone()
    props = (row["props"] if row else None) or {}
    if not isinstance(props, dict):
        props = {}
    out |= set(instance_required_markings(props))

    parents = conn.execute(
        """
        SELECT dst_type, dst_id FROM graph_edge
        WHERE src_type=%s AND src_id=%s AND rel=%s
        """,
        (object_type, object_id, INHERIT_REL),
    ).fetchall()
    for p in parents:
        out |= set(type_required_markings(conn, p["dst_type"]))
        prow = conn.execute(
            "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (p["dst_type"], p["dst_id"]),
        ).fetchone()
        pprops = (prow["props"] if prow else None) or {}
        if isinstance(pprops, dict):
            out |= set(instance_required_markings(pprops))
    return sorted(out)


def can_access_object(
    principal: Principal,
    conn: Any,
    object_type: str,
    object_id: str,
) -> bool:
    """True if markings + optional OpenFGA viewer allow read."""
    try:
        ensure_object_access(principal, conn, object_type, object_id)
        return True
    except ApiError as exc:
        if exc.code == "FORBIDDEN":
            return False
        raise


def ensure_object_access(
    principal: Principal,
    conn: Any,
    object_type: str,
    object_id: str,
) -> None:
    """Object-level Marking (JWT ∪ FGA bearer) AND OpenFGA viewer (when tuples)."""
    ensure_markings(
        principal,
        effective_markings(conn, object_type, object_id),
        conn=conn,
    )
    from aos_api.openfga import ensure_object_viewer

    ensure_object_viewer(principal, object_type, object_id, conn=conn)
