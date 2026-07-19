"""TWA.8 — R-ISO-04 tenant prefix for object store / vector / wiki."""
from __future__ import annotations

import re
from typing import Any

from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.tenant-prefix")

_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_id(value: str, *, field: str) -> str:
    v = (value or "").strip()
    if not v or not _SAFE.match(v):
        raise ApiError(
            code="VALIDATION",
            message=f"invalid {field} for storage prefix",
            status_code=400,
            details={"field": field},
        )
    return v


def tenant_key_prefix(org_id: str, project_id: str) -> str:
    o = _safe_id(org_id, field="org_id")
    p = _safe_id(project_id, field="project_id")
    return f"{o}/{p}/"


def build_object_key(org_id: str, project_id: str, *parts: str) -> str:
    prefix = tenant_key_prefix(org_id, project_id)
    cleaned = [str(p).strip().strip("/") for p in parts if str(p).strip()]
    return prefix + "/".join(cleaned)


def assert_object_key_tenant(key: str, org_id: str, project_id: str) -> None:
    expected = tenant_key_prefix(org_id, project_id)
    k = (key or "").lstrip("/")
    if not k.startswith(expected):
        log.warning(
            "object_key_denied org=%s project=%s",
            org_id,
            project_id,
        )
        raise ApiError(
            code="FORBIDDEN",
            message="object key outside current workspace prefix",
            status_code=403,
            details={"code": "TENANT_PREFIX"},
        )


def scoped_collection_name(org_id: str, project_id: str, logical: str) -> str:
    o = _safe_id(org_id, field="org_id")
    p = _safe_id(project_id, field="project_id")
    name = (logical or "").strip()
    if not name:
        raise ApiError(code="VALIDATION", message="collection required", status_code=400)
    marker = f"{o}__{p}__"
    if name.startswith(marker):
        return name
    # reject foreign tenant prefix
    if "__" in name:
        parts = name.split("__", 2)
        if len(parts) >= 2 and (parts[0] != o or parts[1] != p):
            log.warning(
                "collection_denied org=%s project=%s",
                org_id,
                project_id,
            )
            raise ApiError(
                code="FORBIDDEN",
                message="vector collection outside current workspace",
                status_code=403,
                details={"code": "TENANT_PREFIX"},
            )
    safe_logical = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:80]
    return f"{marker}{safe_logical}"


def wiki_space_id(org_id: str, project_id: str) -> str:
    o = _safe_id(org_id, field="org_id")
    p = _safe_id(project_id, field="project_id")
    return f"wiki:{o}:{p}"


def migrate_prefix_dry_run(
    keys: list[str],
    org_id: str,
    project_id: str,
) -> dict[str, Any]:
    """Report keys missing current tenant prefix (no mutation)."""
    expected = tenant_key_prefix(org_id, project_id)
    missing: list[str] = []
    ok: list[str] = []
    for raw in keys:
        k = (raw or "").lstrip("/")
        if k.startswith(expected):
            ok.append(k)
        else:
            missing.append(k)
    log.info(
        "prefix_dry_run org=%s project=%s ok=%s missing=%s",
        org_id,
        project_id,
        len(ok),
        len(missing),
    )
    return {
        "orgId": org_id,
        "projectId": project_id,
        "expectedPrefix": expected,
        "okCount": len(ok),
        "missingCount": len(missing),
        "missingSample": missing[:20],
    }
