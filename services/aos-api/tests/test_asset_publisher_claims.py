"""Publisher scopes come only from verified, normalized identity claims."""
from __future__ import annotations

import base64
import json
from typing import Any, cast

import pytest

from aos_api.auth import resolve_principal
from aos_api.errors import ApiError
from aos_api.oidc import issue_dev_token


def _token(*, asset_publishers: Any = None, include_claim: bool = True) -> str:
    kwargs: dict[str, Any] = {
        "subject": "publisher-user",
        "org_id": "org-a",
        "project_id": "project-a",
    }
    if include_claim:
        kwargs["asset_publishers"] = asset_publishers
    return cast(str, issue_dev_token(**kwargs)["accessToken"])


def test_verified_jwt_exposes_immutable_normalized_publisher_scope() -> None:
    principal = resolve_principal(
        token=_token(asset_publishers=["aos", "partner.one", "*"])
    )

    assert principal.asset_publishers == frozenset({"aos", "partner.one", "*"})
    with pytest.raises(AttributeError):
        principal.asset_publishers.add("forged")  # type: ignore[attr-defined]


def test_verified_jwt_without_publisher_claim_has_no_implicit_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")

    principal = resolve_principal(token=_token(include_claim=False))

    assert principal.token_kind == "oidc"
    assert principal.asset_publishers == frozenset()


def test_verified_jwt_accepts_an_explicit_empty_publisher_scope() -> None:
    principal = resolve_principal(token=_token(asset_publishers=[]))

    assert principal.asset_publishers == frozenset()


@pytest.mark.parametrize(
    "invalid_claim",
    (
        "aos",
        {"publisher": "aos"},
        [1],
        [""],
        [" aos"],
        ["aos "],
        ["AOS"],
        ["aos/other"],
        ["aos", "aos"],
        ["a" * 121],
        [f"publisher-{index}" for index in range(501)],
    ),
)
def test_verified_jwt_rejects_malformed_publisher_claim(
    invalid_claim: Any,
) -> None:
    with pytest.raises(ApiError) as error:
        resolve_principal(token=_token(asset_publishers=invalid_claim))

    assert error.value.code == "AUTH_INVALID"
    assert error.value.status_code == 401


def test_verified_jwt_rejects_an_explicit_null_publisher_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "aos_api.auth.verify_access_token",
        lambda _token: {
            "sub": "publisher-user",
            "org_id": "org-a",
            "project_id": "project-a",
            "asset_publishers": None,
        },
    )

    with pytest.raises(ApiError) as error:
        resolve_principal(token="header.payload.signed-token")

    assert error.value.code == "AUTH_INVALID"
    assert error.value.status_code == 401


def test_tampering_publisher_claim_after_signing_is_rejected() -> None:
    token = _token(asset_publishers=["aos"])
    header, payload, signature = token.split(".")
    decoded = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    decoded["asset_publishers"] = ["forged.publisher"]
    tampered_payload = base64.urlsafe_b64encode(
        json.dumps(decoded, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")

    with pytest.raises(ApiError) as error:
        resolve_principal(token=f"{header}.{tampered_payload}.{signature}")

    assert error.value.code == "AUTH_INVALID"
    assert error.value.status_code == 401


def test_bearer_dev_gets_local_default_scope_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "1")

    principal = resolve_principal(token="dev")

    assert principal.token_kind == "dev"
    assert principal.asset_publishers == frozenset({"aos"})


def test_bearer_dev_cannot_get_default_scope_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")

    with pytest.raises(ApiError) as error:
        resolve_principal(token="dev")

    assert error.value.code == "AUTH_DEV_DISABLED"
    assert error.value.status_code == 401
