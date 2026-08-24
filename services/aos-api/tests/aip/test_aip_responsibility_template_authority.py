"""Installed Bundle artifact authority tests for ResponsibilityTemplate refs."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_responsibility_template_authority import InstalledProductionProfileResolver
from aos_api.tenant_scope import TenantScope


ARTIFACT_REF = (
    "bundle://aos/solution.ecommerce.growth@1.4.0/"
    "content/production-profiles/ecommerce.content-campaign.json"
)
ARTIFACT_HASH = "a" * 64
BUNDLE_HASH = "sha256:" + "b" * 64
SIGNATURE_FINGERPRINT = "sha256:" + "c" * 64
EVIDENCE_REVISION = "sha256:" + "d" * 64


def _ref(*, revision: int = 7, content_hash: str = ARTIFACT_HASH) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type="ResponsibilityTemplateRevision",
        resource_id=ARTIFACT_REF,
        revision=revision,
        content_hash=content_hash,
    )


def _row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "installation_id": "00000000-0000-0000-0000-000000000007",
        "active_revision": 7,
        "installation_state": "active",
        "lock_payload": {
            "resolved": [
                {
                    "publisher": "aos",
                    "id": "solution.ecommerce.growth",
                    "version": "1.4.0",
                    "contentHash": BUNDLE_HASH,
                    "signatureFingerprint": SIGNATURE_FINGERPRINT,
                    "releaseEvidenceRevision": EVIDENCE_REVISION,
                }
            ]
        },
        "publisher": "aos",
        "bundle_id": "solution.ecommerce.growth",
        "version": "1.4.0",
        "bundle_content_hash": BUNDLE_HASH,
        "signature": {"algorithm": "Ed25519", "signature": "signed"},
        "status": "published",
        "artifact_ref": ARTIFACT_REF,
        "artifact_digest": "sha256:" + ARTIFACT_HASH,
    }
    row.update(changes)
    return row


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _Connection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.params: tuple[object, ...] | None = None

    def execute(self, query: str, params: tuple[object, ...]) -> _Result:
        assert "bundle_installation" in query
        assert "asset_bundle_artifact" in query
        self.params = params
        return _Result(self.rows)


def _resolver(rows: list[dict[str, Any]]):
    connection = _Connection(rows)

    @contextmanager
    def connect(scope: TenantScope):
        assert scope.key in {
            ("org-org", "dev-project"),
            ("dev-org", "dev-project"),
        }
        yield connection

    return InstalledProductionProfileResolver(connect_factory=connect), connection


def test_exact_active_installed_published_artifact_resolves() -> None:
    resolver, connection = _resolver([_row()])

    assert resolver.resolve(TenantScope("org-org", "dev-project"), _ref()) is True
    assert connection.params == (
        ARTIFACT_REF,
        "org-org",
        "dev-project",
        7,
        ARTIFACT_REF,
    )


def test_wrong_hash_and_old_installation_revision_fail_closed() -> None:
    resolver, _ = _resolver([_row()])
    scope = TenantScope("org-org", "dev-project")

    assert resolver.resolve(scope, _ref(content_hash="0" * 64)) is False
    assert resolver.resolve(scope, _ref(revision=6)) is False


def test_uninstalled_or_cross_tenant_artifact_fails_closed() -> None:
    resolver, _ = _resolver([])

    assert resolver.resolve(TenantScope("org-org", "dev-project"), _ref()) is False
    assert resolver.resolve(TenantScope("dev-org", "dev-project"), _ref()) is False


def test_non_published_unsigned_or_lock_drift_fails_closed() -> None:
    scope = TenantScope("org-org", "dev-project")
    bad_rows = [
        _row(status="revoked"),
        _row(signature=None),
        _row(
            lock_payload={
                "resolved": [
                    {
                        "publisher": "aos",
                        "id": "solution.ecommerce.growth",
                        "version": "1.4.0",
                        "contentHash": "sha256:" + "0" * 64,
                        "signatureFingerprint": SIGNATURE_FINGERPRINT,
                        "releaseEvidenceRevision": EVIDENCE_REVISION,
                    }
                ]
            }
        ),
    ]

    for row in bad_rows:
        resolver, _ = _resolver([row])
        assert resolver.resolve(scope, _ref()) is False


def test_unknown_resource_type_and_database_failure_fail_closed() -> None:
    resolver, _ = _resolver([_row()])
    wrong_type = ExactRevisionRef(
        resource_type="EvalProfileRevision",
        resource_id=ARTIFACT_REF,
        revision=7,
        content_hash=ARTIFACT_HASH,
    )
    assert resolver.resolve(TenantScope("org-org", "dev-project"), wrong_type) is False

    @contextmanager
    def broken_connect(scope: TenantScope):
        _ = scope
        raise RuntimeError("registry unavailable")
        yield

    broken = InstalledProductionProfileResolver(connect_factory=broken_connect)
    assert broken.resolve(TenantScope("org-org", "dev-project"), _ref()) is False
