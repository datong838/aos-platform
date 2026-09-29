"""Only the byte gate is exercised here; no live G2 source is certified."""

import hashlib

import pytest

from aos_api.aip_eval_object_reader import (
    MAX_EVAL_OBJECT_BYTES,
    EvalObjectReadBlocked,
    read_verified_eval_object,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
KEY = "org-org/dev-project/evals/d01/source-v1.json"
BODY = b'{"schemaVersion":"isolated-byte-test"}'
DIGEST = hashlib.sha256(BODY).hexdigest()


def test_eval_object_reader_returns_only_exact_tenant_scoped_bytes() -> None:
    seen = []

    def reader(key: str, max_bytes: int) -> bytes:
        seen.append((key, max_bytes))
        return BODY

    assert read_verified_eval_object(SCOPE, KEY, DIGEST, reader=reader) == BODY
    assert seen == [(KEY, MAX_EVAL_OBJECT_BYTES)]


def test_eval_object_reader_default_uses_bounded_s3_get(monkeypatch) -> None:
    seen = []

    def s3_get(*, key: str, max_bytes: int) -> bytes:
        seen.append((key, max_bytes))
        return BODY

    monkeypatch.setattr("aos_api.aip_eval_object_reader.get_bytes", s3_get)
    assert read_verified_eval_object(SCOPE, KEY, DIGEST) == BODY
    assert seen == [(KEY, MAX_EVAL_OBJECT_BYTES)]


@pytest.mark.parametrize("key", [
    "dev-org/dev-project/evals/d01/source-v1.json",
    "org-org/dev-project/mediasets/d01/source-v1.json",
    "org-org/dev-project/evals/../other/source.json",
    "org-org/dev-project/evals//source.json",
    "org-org/dev-project/evals/%2e%2e/source.json",
])
def test_eval_object_reader_rejects_noncanonical_or_foreign_key_before_read(key: str) -> None:
    def forbidden_reader(_key: str, _max_bytes: int) -> bytes:
        raise AssertionError("foreign object was read")

    with pytest.raises(EvalObjectReadBlocked):
        read_verified_eval_object(SCOPE, key, DIGEST, reader=forbidden_reader)


def test_eval_object_reader_rejects_missing_large_or_drifted_bytes() -> None:
    with pytest.raises(EvalObjectReadBlocked, match="unavailable"):
        read_verified_eval_object(
            SCOPE, KEY, DIGEST,
            reader=lambda _key, _limit: (_ for _ in ()).throw(FileNotFoundError()),
        )
    with pytest.raises(EvalObjectReadBlocked, match="size"):
        read_verified_eval_object(
            SCOPE, KEY, DIGEST,
            reader=lambda _key, _limit: b"x" * (MAX_EVAL_OBJECT_BYTES + 1),
        )
    with pytest.raises(EvalObjectReadBlocked, match="hash"):
        read_verified_eval_object(
            SCOPE, KEY, DIGEST, reader=lambda _key, _limit: b"different",
        )
