"""Deterministic JSON serialization and SHA-256 hashing for asset manifests."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any


class CanonicalJsonError(ValueError):
    """Raised when a value cannot be represented by the canonical JSON profile."""


def canonical_json(value: object) -> bytes:
    """Return deterministic, compact UTF-8 JSON for a JSON-compatible value.

    The profile intentionally accepts only native JSON container/value types.
    This prevents implicit key coercion and application-specific encoders from
    changing the bytes whose digest or signature is checked.
    """

    _validate_json_value(value, active_container_ids=set(), path="$")
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise CanonicalJsonError("value cannot be encoded as canonical JSON") from exc

    try:
        return rendered.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalJsonError("value contains invalid Unicode data") from exc


def canonical_sha256(value: object) -> str:
    """Return the lowercase, algorithm-qualified digest of canonical JSON."""

    digest = hashlib.sha256(canonical_json(value)).hexdigest()
    return f"sha256:{digest}"


def _validate_json_value(
    value: object,
    *,
    active_container_ids: set[int],
    path: str,
) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalJsonError(f"non-finite number at {path}")
        return

    if isinstance(value, Mapping):
        _enter_container(value, active_container_ids, path)
        try:
            for key, item in value.items():
                if not isinstance(key, str):
                    raise CanonicalJsonError(f"object key at {path} must be a string")
                _validate_json_value(
                    item,
                    active_container_ids=active_container_ids,
                    path=f"{path}.{key}",
                )
        finally:
            active_container_ids.remove(id(value))
        return

    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    ):
        if not isinstance(value, list):
            raise CanonicalJsonError(f"array at {path} must be a list")
        _enter_container(value, active_container_ids, path)
        try:
            for index, item in enumerate(value):
                _validate_json_value(
                    item,
                    active_container_ids=active_container_ids,
                    path=f"{path}[{index}]",
                )
        finally:
            active_container_ids.remove(id(value))
        return

    raise CanonicalJsonError(
        f"unsupported value type at {path}: {type(value).__name__}"
    )


def _enter_container(
    value: Mapping[str, Any] | list[Any],
    active_container_ids: set[int],
    path: str,
) -> None:
    marker = id(value)
    if marker in active_container_ids:
        raise CanonicalJsonError(f"circular reference at {path}")
    active_container_ids.add(marker)
