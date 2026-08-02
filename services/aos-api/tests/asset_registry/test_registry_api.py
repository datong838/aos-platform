"""Contract tests for the M1 canonical Asset Registry API."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from aos_api.asset_registry.contracts import BundleKind
from aos_api.asset_registry.errors import AssetRegistryError, AssetRegistryErrorCode
from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import asset_bundles
from fastapi import FastAPI
from fastapi.testclient import TestClient

_PRINCIPAL = Principal(
    subject="user:registry-editor",
    org_id="org-a",
    project_id="project-a",
    roles=["developer", "asset-publisher"],
    markings=["public"],
    token_kind="test",
)

_ROUTES: tuple[tuple[str, str, dict[str, Any] | None, str], ...] = (
    ("GET", "/v1/asset-bundles", None, "list_bundles"),
    (
        "POST",
        "/v1/asset-bundles",
        {
            "publisher": "pub.one",
            "bundleId": "domain.example",
            "kind": "DomainPack",
            "displayName": "Example Domain",
        },
        "create_bundle",
    ),
    (
        "GET",
        "/v1/asset-bundles/domain.example?publisher=pub.one",
        None,
        "get_bundle",
    ),
    (
        "POST",
        "/v1/asset-bundles/domain.example/versions",
        {
            "bundleSourceRef": "bundle://catalog/domain.example",
            "publisher": "pub.one",
        },
        "create_version",
    ),
    (
        "GET",
        "/v1/asset-bundles/domain.example/versions/1.2.3?publisher=pub.one",
        None,
        "get_version",
    ),
    (
        "POST",
        "/v1/asset-bundles/domain.example/versions/1.2.3/validate",
        {"publisher": "pub.body"},
        "validate",
    ),
    (
        "POST",
        "/v1/asset-bundles/domain.example/versions/1.2.3/publish?publisher=pub.query",
        {},
        "publish",
    ),
    (
        "POST",
        "/v1/asset-bundles/domain.example/versions/1.2.3/deprecate?publisher=pub.one",
        {"publisher": "pub.one", "reason": "superseded"},
        "deprecate",
    ),
    (
        "POST",
        "/v1/asset-bundles/domain.example/versions/1.2.3/revoke",
        {"reason": "security incident"},
        "revoke",
    ),
)


class FakeRegistryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.failures: dict[str, AssetRegistryError] = {}

    def _call(self, operation: str, **kwargs: Any) -> Any:
        self.calls.append((operation, kwargs))
        failure = self.failures.get(operation)
        if failure is not None:
            raise failure
        if operation == "list_bundles":
            return [{"bundleId": "domain.example", "publisher": "pub.one"}]
        return {"operation": operation}

    def list_bundles(self) -> list[dict[str, Any]]:
        return self._call("list_bundles")

    def create_bundle(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("create_bundle", **kwargs)

    def get_bundle(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("get_bundle", **kwargs)

    def create_version(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("create_version", **kwargs)

    def get_version(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("get_version", **kwargs)

    def validate(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("validate", **kwargs)

    def publish(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("publish", **kwargs)

    def deprecate(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("deprecate", **kwargs)

    def revoke(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("revoke", **kwargs)


def _make_app(fake_service: FakeRegistryService, *, authenticated: bool) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(asset_bundles.router)
    app.dependency_overrides[asset_bundles.get_asset_registry_service] = (
        lambda: fake_service
    )
    if authenticated:
        app.dependency_overrides[require_principal] = lambda: _PRINCIPAL
    return app


@pytest.fixture()
def fake_service() -> FakeRegistryService:
    return FakeRegistryService()


@pytest.fixture()
def client(fake_service: FakeRegistryService) -> Iterator[TestClient]:
    app = _make_app(fake_service, authenticated=True)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _request(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, Any] | None,
):
    if body is None:
        return client.request(method, path)
    return client.request(method, path, json=body)


@pytest.mark.parametrize(("method", "path", "body", "_operation"), _ROUTES)
def test_every_registry_route_requires_a_principal(
    fake_service: FakeRegistryService,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    _operation: str,
) -> None:
    with TestClient(
        _make_app(fake_service, authenticated=False),
        raise_server_exceptions=False,
    ) as unauthenticated:
        response = _request(unauthenticated, method, path, body)

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"
    assert fake_service.calls == []


def test_all_nine_routes_delegate_with_principal_and_publisher(
    client: TestClient,
    fake_service: FakeRegistryService,
) -> None:
    responses = [
        _request(client, method, path, body) for method, path, body, _op in _ROUTES
    ]

    assert [response.status_code for response in responses] == [
        200,
        201,
        200,
        201,
        200,
        200,
        200,
        200,
        200,
    ]
    assert responses[0].json() == [
        {"bundleId": "domain.example", "publisher": "pub.one"}
    ]
    calls = dict(fake_service.calls)
    assert list(calls) == [case[3] for case in _ROUTES]
    assert calls["create_bundle"] == {
        "publisher": "pub.one",
        "bundle_id": "domain.example",
        "kind": BundleKind.DOMAIN_PACK,
        "display_name": "Example Domain",
        "actor": _PRINCIPAL.subject,
        "roles": _PRINCIPAL.roles,
    }
    assert calls["get_bundle"] == {
        "bundle_id": "domain.example",
        "publisher": "pub.one",
    }
    assert calls["create_version"] == {
        "bundle_id": "domain.example",
        "source_ref": "bundle://catalog/domain.example",
        "actor": _PRINCIPAL.subject,
        "roles": _PRINCIPAL.roles,
        "publisher": "pub.one",
    }
    assert calls["get_version"] == {
        "bundle_id": "domain.example",
        "version": "1.2.3",
        "publisher": "pub.one",
    }
    assert calls["validate"]["publisher"] == "pub.body"
    assert calls["publish"]["publisher"] == "pub.query"
    assert calls["deprecate"]["reason"] == "superseded"
    assert calls["revoke"]["reason"] == "security incident"
    for operation in ("validate", "publish", "deprecate", "revoke"):
        assert calls[operation]["actor"] == _PRINCIPAL.subject
        assert calls[operation]["roles"] == _PRINCIPAL.roles


@pytest.mark.parametrize(
    ("path", "body"),
    (
        (
            "/v1/asset-bundles",
            {
                "publisher": "pub.one",
                "bundleId": "domain.example",
                "kind": "DomainPack",
                "displayName": "Example",
                "validated": True,
            },
        ),
        (
            "/v1/asset-bundles/domain.example/versions",
            {
                "bundleSourceRef": "bundle://catalog/domain.example",
                "contentHash": "sha256:client-assertion",
            },
        ),
        (
            "/v1/asset-bundles/domain.example/versions",
            {"bundleSourceRef": "/tmp/domain.example"},
        ),
        (
            "/v1/asset-bundles/domain.example/versions",
            {"bundleSourceRef": "https://example.invalid/domain.example"},
        ),
        (
            "/v1/asset-bundles/domain.example/versions/1.2.3/validate",
            {"validated": True},
        ),
        (
            "/v1/asset-bundles/domain.example/versions/1.2.3/publish",
            {"contentHash": "sha256:client-assertion"},
        ),
        (
            "/v1/asset-bundles/domain.example/versions/1.2.3/publish",
            {"privateKey": "client-supplied-key"},
        ),
        (
            "/v1/asset-bundles/domain.example/versions/1.2.3/deprecate",
            {"localPath": "/tmp/domain.example"},
        ),
        (
            "/v1/asset-bundles/domain.example/versions/1.2.3/revoke",
            {"url": "https://example.invalid/domain.example"},
        ),
    ),
)
def test_write_bodies_reject_forged_or_non_server_derived_fields(
    client: TestClient,
    fake_service: FakeRegistryService,
    path: str,
    body: dict[str, Any],
) -> None:
    response = client.post(path, json=body)

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert fake_service.calls == []


def test_query_and_body_publisher_must_not_disagree(
    client: TestClient,
    fake_service: FakeRegistryService,
) -> None:
    response = client.post(
        "/v1/asset-bundles/domain.example/versions?publisher=pub.query",
        json={
            "bundleSourceRef": "bundle://catalog/domain.example",
            "publisher": "pub.body",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "MANIFEST_INVALID"
    assert fake_service.calls == []


@pytest.mark.parametrize(("method", "path", "body", "operation"), _ROUTES)
def test_every_route_maps_registry_errors_to_the_stable_envelope(
    client: TestClient,
    fake_service: FakeRegistryService,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    operation: str,
) -> None:
    fake_service.failures[operation] = AssetRegistryError(
        AssetRegistryErrorCode.NOT_FOUND,
        "registry object was not found",
        details={"resource": operation},
    )

    response = _request(client, method, path, body)

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["message"] == "registry object was not found"
    assert response.json()["details"] == {"resource": operation}
    assert set(response.json()) == {"code", "message", "details", "traceId"}


@pytest.mark.parametrize(
    ("error_code", "http_status"),
    (
        (AssetRegistryErrorCode.MANIFEST_INVALID, 400),
        (AssetRegistryErrorCode.VERSION_INVALID, 400),
        (AssetRegistryErrorCode.SIGNATURE_INVALID, 400),
        (AssetRegistryErrorCode.BUNDLE_VERSION_IMMUTABLE, 409),
        (AssetRegistryErrorCode.DEPENDENCY_CONFLICT, 409),
        (AssetRegistryErrorCode.DEPENDENCY_CYCLE, 409),
        (AssetRegistryErrorCode.REVISION_CONFLICT, 409),
        (AssetRegistryErrorCode.IDEMPOTENCY_CONFLICT, 409),
        (AssetRegistryErrorCode.APPROVAL_STALE, 409),
        (AssetRegistryErrorCode.DUTY_SEPARATION_REQUIRED, 403),
        (AssetRegistryErrorCode.PREFLIGHT_FAILED, 422),
        (AssetRegistryErrorCode.VERIFICATION_FAILED, 422),
        (AssetRegistryErrorCode.ROLLBACK_BLOCKED, 409),
        (AssetRegistryErrorCode.NOT_FOUND, 404),
    ),
)
def test_all_frozen_registry_error_codes_keep_their_http_status(
    client: TestClient,
    fake_service: FakeRegistryService,
    error_code: AssetRegistryErrorCode,
    http_status: int,
) -> None:
    fake_service.failures["list_bundles"] = AssetRegistryError(
        error_code,
        "safe registry failure",
        details={"gate": "m1"},
    )

    response = client.get("/v1/asset-bundles")

    assert response.status_code == http_status
    assert response.json()["code"] == error_code.value
    assert response.json()["details"] == {"gate": "m1"}
    assert set(response.json()) == {"code", "message", "details", "traceId"}


def test_service_provider_uses_only_server_controlled_bundle_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repository"
    catalog_root = repository_root / "bundles"
    server_root = tmp_path / "server-bundles"
    catalog_root.mkdir(parents=True)
    server_root.mkdir()
    captured: dict[str, Any] = {}

    class StoreSpy:
        def __init__(self) -> None:
            captured["store"] = self

    class LoaderSpy:
        def __init__(
            self,
            allowlist_roots: dict[str, Path],
            trust_roots: object | None = None,
        ) -> None:
            captured["allowlist_roots"] = allowlist_roots
            captured["trust_roots"] = trust_roots

    monkeypatch.setattr(asset_bundles, "_REPOSITORY_ROOT", repository_root)
    monkeypatch.setattr(asset_bundles, "PostgresRegistryStore", StoreSpy)
    monkeypatch.setattr(asset_bundles, "ManifestLoader", LoaderSpy)
    monkeypatch.setenv("AOS_BUNDLE_ROOT", str(server_root))
    asset_bundles.get_asset_registry_service.cache_clear()
    try:
        service = asset_bundles.get_asset_registry_service()
    finally:
        asset_bundles.get_asset_registry_service.cache_clear()

    assert service.__class__ is asset_bundles.RegistryService
    assert captured["store"].__class__ is StoreSpy
    assert captured["allowlist_roots"] == {
        "catalog": catalog_root,
        "server": server_root,
    }
    assert captured["trust_roots"] is None
