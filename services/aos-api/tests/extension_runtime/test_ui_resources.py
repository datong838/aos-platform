from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime, timezone
from types import SimpleNamespace

from aos_api.asset_registry.composition_contracts import InstallationResponse
from aos_api.extension_runtime import ui_resources
from aos_api.extension_runtime.ui_resources import FrontendUiManifest, ProductionUiSessionResolver


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64
HASH_D = "sha256:" + "d" * 64
INSTALLATION_ID = "11111111-1111-4111-8111-111111111111"


class _Result:
    def __init__(self, *, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _Connection:
    def execute(self, sql, *_args):
        if "clock_timestamp" in sql:
            return _Result(one={"checked_at": datetime.now(timezone.utc)})
        if "FROM asset_bundle_version" in sql:
            return _Result(many=[{"publisher": "aos", "bundle_id": "test.extension", "version": "1.0.0"}])
        return _Result()


class _Policy:
    def __init__(self):
        self.calls = []

    def snapshot(self):
        return self

    def evaluate(self, record, **kwargs):
        self.calls.append((record, kwargs))


class _Loader:
    def __init__(self, manifest, frontend_manifest):
        self.frontend_manifest = frontend_manifest
        self.loaded = SimpleNamespace(
            content_hash=HASH_C,
            manifest=manifest,
            artifacts=[
                SimpleNamespace(relative_path="frontend/manifest.json", digest=HASH_A),
                SimpleNamespace(relative_path="frontend/index.html", digest=HASH_B),
            ],
        )
        self.read_calls = []

    def load(self, source_ref):
        assert source_ref == "bundle://catalog/test-extension"
        return self.loaded

    def read_verified_artifact(self, source_ref, relative_path, *, expected_digest, limit):
        self.read_calls.append((source_ref, relative_path, expected_digest, limit))
        return json.dumps(self.frontend_manifest).encode()


def _installation():
    return InstallationResponse.model_construct(
        installation_id=INSTALLATION_ID,
        current_revision=5,
        current=SimpleNamespace(
            composition_id="22222222-2222-4222-8222-222222222222",
            lock_revision=2,
        ),
    )


def test_frontend_manifest_rejects_route_traversal_and_overlapping_operations() -> None:
    base = {
        "schemaVersion": "aos.dev/frontend-runtime/v1alpha1",
        "title": "隔离扩展",
        "entrypoint": "frontend/index.html",
        "initialRoute": "/workshop",
        "routeClaims": ["/workshop", "/workshop/*"],
        "readOperationClaims": ["read.orders"],
        "commandOperationClaims": ["command.content.create"],
    }
    assert FrontendUiManifest.model_validate(base).initialRoute == "/workshop"
    try:
        FrontendUiManifest.model_validate({**base, "initialRoute": "/workshop/../admin"})
        raise AssertionError("route traversal must be rejected")
    except ValueError:
        pass
    try:
        FrontendUiManifest.model_validate({**base, "commandOperationClaims": ["read.orders"]})
        raise AssertionError("overlapping operation claims must be rejected")
    except ValueError:
        pass


def test_production_resolver_derives_session_from_exact_lock_release_and_artifacts(monkeypatch) -> None:
    frontend = SimpleNamespace(manifest="frontend/manifest.json", artifact_hash=HASH_A)
    manifest = SimpleNamespace(spec=SimpleNamespace(runtime=SimpleNamespace(frontend=frontend)))
    record = SimpleNamespace(
        content_hash=HASH_C,
        manifest=manifest,
        evidence=[SimpleNamespace(type=SimpleNamespace(value="content_hash"), artifact_ref="bundle://catalog/test-extension/bundle.yaml")],
    )
    selected = SimpleNamespace(
        publisher="aos",
        id="test.extension",
        version="1.0.0",
        content_hash=HASH_C,
        signature_fingerprint=HASH_D,
        release_evidence_revision=HASH_A,
    )
    monkeypatch.setattr(ui_resources, "load_stored_lock", lambda *_args, **_kwargs: (None, SimpleNamespace(payload=SimpleNamespace(resolved=[selected]))))
    monkeypatch.setattr(ui_resources, "_record_from_row", lambda _row: record)
    frontend_manifest = {
        "schemaVersion": "aos.dev/frontend-runtime/v1alpha1",
        "title": "隔离扩展",
        "entrypoint": "frontend/index.html",
        "initialRoute": "/workshop",
        "routeClaims": ["/workshop", "/workshop/*"],
        "readOperationClaims": ["read.orders"],
        "commandOperationClaims": ["command.content.create"],
    }
    loader = _Loader(manifest, frontend_manifest)
    policy = _Policy()
    resolver = ProductionUiSessionResolver(
        connect_factory=lambda: nullcontext(_Connection()),
        release_policy=policy,
        loader=loader,
        resource_origin="http://127.0.0.1:18182/extensions",
    )

    session = resolver(
        installation=_installation(),
        org_id="org-org",
        project_id="dev-project",
        installation_id=INSTALLATION_ID,
        installation_revision=5,
        generation="33333333-3333-4333-8333-333333333333",
        execution_epoch=3,
        roles=["admin"],
        markings=["public"],
    )

    assert session is not None
    assert session.resourceHash == HASH_B
    assert session.signedResourceUrl.count("contentHash=") == 1
    assert "/aos/test.extension/1.0.0/frontend/index.html?" in session.signedResourceUrl
    assert loader.read_calls == [("bundle://catalog/test-extension", "frontend/manifest.json", HASH_A, 65_536)]
    assert policy.calls[0][1]["expected_signature_fingerprint"] == HASH_D


def test_production_resolver_without_server_resource_origin_fails_closed() -> None:
    resolver = ProductionUiSessionResolver(
        connect_factory=lambda: (_ for _ in ()).throw(AssertionError("must not connect")),
        release_policy=object(),
        loader=object(),
        resource_origin=None,
    )
    assert resolver(
        installation=_installation(),
        org_id="org-org",
        project_id="dev-project",
        installation_id=INSTALLATION_ID,
        installation_revision=5,
        generation="33333333-3333-4333-8333-333333333333",
        execution_epoch=3,
        roles=["admin"],
        markings=["public"],
    ) is None
