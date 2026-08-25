"""Installed Bundle artifact authority tests for ResponsibilityTemplate refs."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

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
        "relative_path": (
            "content/production-profiles/ecommerce.content-campaign.json"
        ),
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


def _resolver(rows: list[dict[str, Any]], *, release_root: Path | None = None):
    connection = _Connection(rows)

    @contextmanager
    def connect(scope: TenantScope):
        assert scope.key in {
            ("org-org", "dev-project"),
            ("dev-org", "dev-project"),
        }
        yield connection

    return (
        InstalledProductionProfileResolver(
            connect_factory=connect,
            release_root=release_root,
        ),
        connection,
    )


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
        resource_type="EvalSuiteRevision",
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


def _production_profile_payload() -> dict[str, object]:
    return {
        "schema": "aos.ecommerce-production-profile/v1",
        "moduleId": "ecommerce.content-campaign",
        "profileRevision": 1,
        "brief": {
            "mode": "owned",
            "briefType": "campaign-content",
            "requiredFields": ["objective"],
            "sourceResponsibilityPreserved": True,
        },
        "evidenceSelection": {
            "requiredFacts": ["audienceEvidence", "brandPolicy"],
            "requireProvenance": True,
            "requireFreshness": True,
            "requireNegativeEvidence": True,
        },
        "eval": {
            "gates": ["fact", "brand", "approval"],
            "failClosed": True,
            "sameRevisionRequired": True,
        },
        "responsibility": {
            "slots": [
                {
                    "slotId": "content.owner",
                    "responsibilityType": "maker",
                    "atomicSkillIds": ["strategy.plan", "copy.generate"],
                    "protected": False,
                    "mergeAllowed": True,
                    "returnStage": "prepare",
                },
                {
                    "slotId": "content.review",
                    "responsibilityType": "independent_review",
                    "atomicSkillIds": ["content.review"],
                    "protected": True,
                    "mergeAllowed": False,
                    "returnStage": "prepare",
                }
            ],
            "handoffRequired": True,
            "reassignmentRequiresCanonicalDecision": True,
        },
        "contributionProjection": {
            "showAtomicSkillAttribution": True,
            "showLogicRevision": True,
            "showCoworkerBinding": True,
            "showBlockers": True,
        },
    }


def _profile_ref(content_hash: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type="ProductionProfileRevision",
        resource_id=ARTIFACT_REF,
        revision=7,
        content_hash=content_hash,
    )


def test_verified_profile_loads_from_immutable_release_mirror(tmp_path: Path) -> None:
    raw = json.dumps(
        _production_profile_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    relative_path = "content/production-profiles/ecommerce.content-campaign.json"
    artifact_path = tmp_path / "solution.ecommerce.growth" / "1.4.0" / relative_path
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(raw)
    resolver, connection = _resolver(
        [
            _row(
                artifact_digest=f"sha256:{digest}",
                relative_path=relative_path,
            )
        ],
        release_root=tmp_path,
    )

    profile = resolver.load_profile(
        TenantScope("org-org", "dev-project"), _profile_ref(digest)
    )

    assert profile is not None
    assert profile.module_id == "ecommerce.content-campaign"
    assert profile.responsibility.slots[0].atomic_skill_ids == [
        "strategy.plan",
        "copy.generate",
    ]
    assert connection.params is not None


def test_profile_loader_fails_closed_on_mirror_drift_or_path_escape(
    tmp_path: Path,
) -> None:
    raw = json.dumps(
        _production_profile_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    release_path = (
        tmp_path
        / "solution.ecommerce.growth"
        / "1.4.0"
        / "content/production-profiles/ecommerce.content-campaign.json"
    )
    release_path.parent.mkdir(parents=True)
    release_path.write_bytes(raw + b"\n")
    scope = TenantScope("org-org", "dev-project")

    resolver, _ = _resolver(
        [_row(artifact_digest=f"sha256:{digest}")],
        release_root=tmp_path,
    )
    assert resolver.load_profile(scope, _profile_ref(digest)) is None

    escaped, _ = _resolver(
        [
            _row(
                artifact_digest=f"sha256:{digest}",
                relative_path="../outside.json",
            )
        ],
        release_root=tmp_path,
    )
    assert escaped.load_profile(scope, _profile_ref(digest)) is None


@pytest.mark.parametrize(
    ("relative_path", "resource_type", "loader_name", "expected_profile"),
    [
        (
            "content/media-production-templates/standard.responsibility.json",
            "ResponsibilityTemplateRevision",
            "load_media_responsibility_template",
            "STANDARD",
        ),
        (
            "content/media-production-templates/full.stage.json",
            "StageTemplateRevision",
            "load_media_stage_template",
            "FULL",
        ),
    ],
)
def test_signed_installation_loads_exact_media_templates(
    tmp_path: Path,
    relative_path: str,
    resource_type: str,
    loader_name: str,
    expected_profile: str,
) -> None:
    source = (
        Path(__file__).resolve().parents[4]
        / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0"
        / relative_path
    )
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    artifact_ref = (
        "bundle://aos/solution.ecommerce.growth@1.4.0/" + relative_path
    )
    artifact_path = (
        tmp_path / "solution.ecommerce.growth" / "1.4.0" / relative_path
    )
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(raw)
    resolver, _ = _resolver(
        [
            _row(
                artifact_ref=artifact_ref,
                relative_path=relative_path,
                artifact_digest=f"sha256:{digest}",
            )
        ],
        release_root=tmp_path,
    )
    ref = ExactRevisionRef(
        resourceType=resource_type,
        resourceId=artifact_ref,
        revision=7,
        contentHash=digest,
    )

    loaded = getattr(resolver, loader_name)(
        TenantScope("org-org", "dev-project"), ref
    )

    assert loaded is not None
    assert loaded.profile.value == expected_profile


def test_media_template_load_fails_closed_when_unsigned_revoked_or_drifted(
    tmp_path: Path,
) -> None:
    relative_path = "content/media-production-templates/lite.stage.json"
    source = (
        Path(__file__).resolve().parents[4]
        / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0"
        / relative_path
    )
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    artifact_ref = (
        "bundle://aos/solution.ecommerce.growth@1.4.0/" + relative_path
    )
    artifact_path = (
        tmp_path / "solution.ecommerce.growth" / "1.4.0" / relative_path
    )
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(raw)
    ref = ExactRevisionRef(
        resourceType="StageTemplateRevision",
        resourceId=artifact_ref,
        revision=7,
        contentHash=digest,
    )
    scope = TenantScope("org-org", "dev-project")

    for row in (
        _row(
            artifact_ref=artifact_ref,
            relative_path=relative_path,
            artifact_digest=f"sha256:{digest}",
            signature=None,
        ),
        _row(
            artifact_ref=artifact_ref,
            relative_path=relative_path,
            artifact_digest=f"sha256:{digest}",
            status="revoked",
        ),
        _row(
            artifact_ref=artifact_ref,
            relative_path=relative_path,
            artifact_digest="sha256:" + "0" * 64,
        ),
    ):
        resolver, _ = _resolver([row], release_root=tmp_path)
        assert resolver.load_media_stage_template(scope, ref) is None

    resolver, _ = _resolver([], release_root=tmp_path)
    assert resolver.load_media_stage_template(
        TenantScope("dev-org", "dev-project"), ref
    ) is None
