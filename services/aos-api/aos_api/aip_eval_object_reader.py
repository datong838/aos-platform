"""Bounded tenant-scoped object bytes for a future G2 Eval source authority."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

from aos_api.object_store import get_bytes
from aos_api.tenant_prefix import tenant_key_prefix
from aos_api.tenant_scope import TenantScope


MAX_EVAL_OBJECT_BYTES = 2 * 1024 * 1024
_SAFE_PART = re.compile(r"[A-Za-z0-9._-]+\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class EvalObjectReadBlocked(RuntimeError):
    code = "EVAL_OBJECT_READ_BLOCKED"


def _read_s3_bytes(key: str, max_bytes: int) -> bytes:
    return get_bytes(key=key, max_bytes=max_bytes)


def read_verified_eval_object(
    scope: TenantScope,
    key: str,
    expected_hash: str,
    *,
    reader: Callable[[str, int], bytes] | None = None,
) -> bytes:
    """Verify exact object bytes; this does not certify redaction or G2 ownership."""
    if not isinstance(key, str) or not isinstance(expected_hash, str):
        raise EvalObjectReadBlocked("eval object reference invalid")
    try:
        prefix = tenant_key_prefix(scope.org_id, scope.project_id) + "evals/"
    except Exception as exc:
        raise EvalObjectReadBlocked("eval tenant scope invalid") from exc
    if not key.startswith(prefix):
        raise EvalObjectReadBlocked("eval object outside tenant eval namespace")
    suffix = key[len(prefix):]
    parts = suffix.split("/")
    if not parts or any(
        part in ("", ".", "..") or _SAFE_PART.fullmatch(part) is None
        for part in parts
    ):
        raise EvalObjectReadBlocked("eval object key is not canonical")
    if _SHA256.fullmatch(expected_hash) is None:
        raise EvalObjectReadBlocked("eval object hash invalid")
    try:
        body = (reader or _read_s3_bytes)(key, MAX_EVAL_OBJECT_BYTES)
    except Exception:
        raise EvalObjectReadBlocked("eval object unavailable") from None
    if type(body) is not bytes or not body or len(body) > MAX_EVAL_OBJECT_BYTES:
        raise EvalObjectReadBlocked("eval object size invalid")
    if hashlib.sha256(body).hexdigest() != expected_hash:
        raise EvalObjectReadBlocked("eval object hash drifted")
    return body
