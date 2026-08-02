from __future__ import annotations

import hashlib

import pytest
from aos_api.asset_registry.canonical_json import (
    CanonicalJsonError,
    canonical_json,
    canonical_sha256,
)


def test_canonical_json_is_sorted_compact_and_utf8() -> None:
    first = {"名称": "资产包", "nested": {"z": 2, "a": [True, None]}}
    second = {"nested": {"a": [True, None], "z": 2}, "名称": "资产包"}

    expected = '{"nested":{"a":[true,null],"z":2},"名称":"资产包"}'.encode()
    assert canonical_json(first) == expected
    assert canonical_json(second) == expected
    assert b"\\u" not in expected


def test_canonical_sha256_is_qualified_and_derived_from_server_bytes() -> None:
    value = {"metadata": {"version": "1.0.0", "id": "solution.example"}}

    canonical = canonical_json(value)
    expected = f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    assert canonical_sha256(value) == expected
    assert len(expected) == len("sha256:") + 64


@pytest.mark.parametrize(
    "value",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {1: "implicit key coercion is forbidden"},
        {"value": (1, 2)},
        {"value": b"bytes"},
    ],
)
def test_canonical_json_rejects_values_outside_native_json(value: object) -> None:
    with pytest.raises(CanonicalJsonError):
        canonical_json(value)


def test_canonical_json_rejects_circular_containers() -> None:
    value: list[object] = []
    value.append(value)

    with pytest.raises(CanonicalJsonError, match="circular reference"):
        canonical_json(value)
