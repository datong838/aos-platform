"""Pure contract tests for the domain-neutral bundle manifest."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.asset_registry import (
    ERROR_HTTP_STATUS,
    AssetNotFoundError,
    AssetRegistryErrorCode,
    BundleArtifact,
    BundleEvidence,
    BundleEvidenceStatus,
    BundleEvidenceType,
    BundleKind,
    BundleManifest,
    BundleSignature,
    BundleVersionStatus,
    LoadedBundle,
    ManifestInvalidError,
)
from aos_api.asset_registry.contracts import (
    ApiContributionClaim,
    NavigationContributionClaim,
    contribution_conflict_keys,
    normalize_api_path,
    normalize_navigation_route,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT
    / "packages/contracts/schemas/asset-bundles/bundle-manifest-v1alpha1.schema.json"
)


def _manifest(*, kind: str = "SolutionPack") -> dict:
    return {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": kind,
        "metadata": {
            "id": "solution.example",
            "version": "1.0.0",
            "displayName": "Example",
            "publisher": "aos",
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.7.0 <2.0.0",
            "dependencies": [{"id": "domain.foundation", "version": "^1.0.0"}],
            "optionalDependencies": [
                {
                    "id": "plugin.search",
                    "version": ">=2.0.0 <3.0.0",
                    "publisher": "aos",
                }
            ],
            "conflicts": [{"id": "solution.legacy"}],
            "exports": {
                "ontology": ["ontology/model.yaml"],
                "agents": ["agents/"],
                "evals": ["evals/suites.yaml"],
            },
            "capabilities": {
                "provides": ["solution.example.v1"],
                "requires": ["aos.plan-envelope.v1"],
            },
            "permissions": {
                "roles": ["asset.reader"],
                "markings": ["internal"],
                "dataScopes": ["objects.read"],
                "actionTypes": [],
            },
            "migrations": {
                "plan": "migrations/plan.json",
                "downgradePolicy": "retain-canonical",
            },
            "preflight": "preflight/spec.yaml",
            "regression": "evals/suites.yaml",
            "rollback": "rollback/manifest.yaml",
        },
    }


@pytest.mark.parametrize("kind", [item.value for item in BundleKind])
def test_all_five_bundle_kinds_round_trip_with_manifest_aliases(kind: str) -> None:
    payload = _manifest(kind=kind)
    manifest = BundleManifest.model_validate(payload)
    assert manifest.kind.value == kind
    assert (
        manifest.model_dump(
            mode="json", by_alias=True, exclude_none=True, exclude_unset=True
        )
        == payload
    )


@pytest.mark.parametrize(
    "kind", ["PlatformRelease", "BundleComposition", "InstanceOverlay", "AssetPack"]
)
def test_non_bundle_kinds_are_rejected(kind: str) -> None:
    with pytest.raises(ValidationError):
        BundleManifest.model_validate(_manifest(kind=kind))


@pytest.mark.parametrize(
    ("location", "field", "value"),
    [
        ((), "contentHash", "sha256:" + "a" * 64),
        (("metadata",), "signatureRef", "sig://forged"),
        (("metadata",), "display_name", "snake-case alias is not accepted"),
        (("spec",), "validated", True),
        (("spec", "permissions"), "secretRef", "secret-value"),
    ],
)
def test_unknown_or_client_asserted_security_fields_are_forbidden(
    location: tuple[str, ...], field: str, value: object
) -> None:
    payload = _manifest()
    target = payload
    for part in location:
        target = target[part]
    target[field] = value
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BundleManifest.model_validate(payload)


@pytest.mark.parametrize(
    "bundle_id",
    [
        "UPPER.case",
        "contains_underscore",
        "../escape",
        "nested/path",
        "nested\\path",
        ".leading",
        "trailing-",
        "two..dots",
    ],
)
def test_bundle_id_is_domain_neutral_and_path_safe(bundle_id: str) -> None:
    payload = _manifest()
    payload["metadata"]["id"] = bundle_id
    with pytest.raises(ValidationError):
        BundleManifest.model_validate(payload)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.yaml",
        "nested/../../escape.yaml",
        "/absolute.yaml",
        "C:/absolute.yaml",
        "nested\\escape.yaml",
        "https://untrusted.invalid/file",
        "nested//file.yaml",
        "nested/./file.yaml",
    ],
)
def test_manifest_references_cannot_escape_the_bundle(path: str) -> None:
    payload = _manifest()
    payload["spec"]["preflight"] = path
    with pytest.raises(ValidationError):
        BundleManifest.model_validate(payload)


def test_manifest_requires_explicit_security_surfaces() -> None:
    fields = [
        "dependencies",
        "optionalDependencies",
        "conflicts",
        "exports",
        "capabilities",
        "permissions",
        "migrations",
        "preflight",
        "regression",
        "rollback",
    ]
    for field in fields:
        payload = _manifest()
        del payload["spec"][field]
        with pytest.raises(ValidationError, match="Field required"):
            BundleManifest.model_validate(payload)


def test_dependencies_are_unique_disjoint_and_not_self_referential() -> None:
    duplicate = _manifest()
    duplicate["spec"]["dependencies"].append(
        {"id": "domain.foundation", "version": ">=1.1.0"}
    )
    with pytest.raises(ValidationError, match="required dependencies must be unique"):
        BundleManifest.model_validate(duplicate)

    overlap = _manifest()
    overlap["spec"]["optionalDependencies"] = [
        {"id": "domain.foundation", "version": "^1.0.0"}
    ]
    with pytest.raises(ValidationError, match="both required and optional"):
        BundleManifest.model_validate(overlap)

    self_reference = _manifest()
    self_reference["spec"]["dependencies"] = [
        {"id": "solution.example", "version": "^1.0.0"}
    ]
    with pytest.raises(
        ValidationError, match="cannot depend on or conflict with itself"
    ):
        BundleManifest.model_validate(self_reference)


def test_capabilities_permissions_and_export_paths_are_not_silently_normalized() -> (
    None
):
    payload = _manifest()
    payload["spec"]["capabilities"]["provides"].append("solution.example.v1")
    with pytest.raises(ValidationError, match="must be unique"):
        BundleManifest.model_validate(payload)


def test_contributions_are_backward_compatible_and_strictly_discriminated() -> None:
    manifest = BundleManifest.model_validate(_manifest())
    assert manifest.spec.contributions == []
    assert (
        "contributions"
        not in manifest.model_dump(mode="json", by_alias=True, exclude_none=False)[
            "spec"
        ]
    )

    payload = _manifest()
    payload["spec"]["contributions"] = [
        {
            "kind": "api",
            "method": "post",
            "path": "/v1/orders/{orderId}/",
            "operationId": "retryOrder",
            "mode": "exclusive",
        },
        {
            "kind": "navigation",
            "route": "/Orders/:orderId/",
            "mode": "shared",
        },
        {
            "kind": "ui",
            "slot": "order.detail.actions",
            "id": "retry-order",
            "mode": "shared",
        },
    ]
    claims = BundleManifest.model_validate(payload).spec.contributions
    assert isinstance(claims[0], ApiContributionClaim)
    assert claims[0].method == "POST"
    assert claims[0].path == "/v1/orders/{orderId}"
    assert isinstance(claims[1], NavigationContributionClaim)
    assert claims[1].route == "/Orders/:orderId"
    assert (
        "contributions"
        in BundleManifest.model_validate(payload).model_dump(
            mode="json", by_alias=True, exclude_none=False
        )["spec"]
    )

    cross_kind = deepcopy(payload)
    cross_kind["spec"]["contributions"][0]["slot"] = "forbidden.cross-kind"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BundleManifest.model_validate(cross_kind)

    snake_alias = deepcopy(payload)
    snake_alias["spec"]["contributions"][0]["operation_id"] = snake_alias["spec"][
        "contributions"
    ][0].pop("operationId")
    with pytest.raises(ValidationError):
        BundleManifest.model_validate(snake_alias)


def test_contribution_normalization_cannot_bypass_collision_keys() -> None:
    assert normalize_api_path("/v1/orders/{id}/") == "/v1/orders/{}"
    assert normalize_api_path("/v1/orders/{orderId}") == "/v1/orders/{}"
    assert normalize_navigation_route("/Orders/:id/") == "/orders/:"
    assert normalize_navigation_route("/orders/:orderId") == "/orders/:"

    first = ApiContributionClaim.model_validate(
        {
            "kind": "api",
            "method": "post",
            "path": "/v1/orders/{id}",
            "operationId": "retryOrder",
            "mode": "exclusive",
        }
    )
    second = ApiContributionClaim.model_validate(
        {
            "kind": "api",
            "method": "POST",
            "path": "/v1/orders/{orderId}/",
            "operationId": "retryOrderAgain",
            "mode": "exclusive",
        }
    )
    assert contribution_conflict_keys(first)[0] == contribution_conflict_keys(second)[0]

    payload = _manifest()
    payload["spec"]["contributions"] = [
        first.model_dump(mode="json", by_alias=True),
        second.model_dump(mode="json", by_alias=True),
    ]
    with pytest.raises(ValidationError, match="conflict keys must be unique"):
        BundleManifest.model_validate(payload)

    for invalid in (
        "/v1/orders/%7Bid%7D",
        "/v1//orders",
        "/v1/orders/{}",
        "/v1/orders/{bad-name}",
        "/v1/orders?state=open",
        "/v1/../orders",
    ):
        with pytest.raises(ValueError):
            normalize_api_path(invalid)


def test_exported_runtime_surfaces_require_signed_contribution_claims() -> None:
    backend = _manifest()
    backend["spec"]["exports"]["backend"] = ["backend/app.py"]
    with pytest.raises(ValidationError, match="require an API contribution"):
        BundleManifest.model_validate(backend)

    ui = _manifest()
    ui["spec"]["exports"]["ui"] = ["ui/index.js"]
    with pytest.raises(ValidationError, match="require a navigation or UI"):
        BundleManifest.model_validate(ui)

    payload = _manifest()
    payload["spec"]["permissions"]["roles"] = [" role.with.spaces "]
    with pytest.raises(ValidationError, match="already normalized"):
        BundleManifest.model_validate(payload)

    payload = _manifest()
    payload["spec"]["exports"]["agents"] = ["agents/", "agents/"]
    with pytest.raises(ValidationError, match="must be unique"):
        BundleManifest.model_validate(payload)


def _artifact(path: str = "bundle.yaml") -> BundleArtifact:
    return BundleArtifact.model_validate(
        {
            "relativePath": path,
            "artifactRef": f"bundle://fixtures/example/{path}",
            "digest": "sha256:" + "a" * 64,
            "size": 128,
            "mediaType": "application/yaml",
        }
    )


def _evidence(**updates) -> BundleEvidence:
    payload = {
        "type": "manifest_validation",
        "artifactRef": "bundle://fixtures/example/evidence/manifest.json",
        "artifactHash": "sha256:" + "b" * 64,
        "status": "valid",
        "observedAt": datetime.now(UTC),
        "expiresAt": datetime.now(UTC) + timedelta(hours=1),
        "revokedAt": None,
        "metadata": {"validator": "v1"},
    }
    payload.update(updates)
    return BundleEvidence.model_validate(payload)


def test_artifact_evidence_signature_and_loaded_bundle_are_strict() -> None:
    artifact = _artifact()
    evidence = _evidence()
    signature = BundleSignature.model_validate(
        {
            "algorithm": "Ed25519",
            "keyId": "test-key",
            "signature": "base64-signature",
            "signedAt": datetime.now(UTC),
        }
    )
    loaded = LoadedBundle.model_validate(
        {
            "sourceRef": "bundle://fixtures/example",
            "manifest": _manifest(),
            "artifacts": [artifact],
            "evidence": [evidence],
            "contentHash": "sha256:" + "c" * 64,
            "signature": signature,
            "loadedAt": datetime.now(UTC),
        }
    )
    assert loaded.manifest.metadata.id == "solution.example"
    assert loaded.artifacts[0].size == 128

    invalid = loaded.model_dump(mode="python", by_alias=True)
    invalid["artifacts"][0]["size"] = "128"
    with pytest.raises(ValidationError):
        LoadedBundle.model_validate(invalid)


def test_loaded_bundle_rejects_untrusted_source_and_duplicate_indexes() -> None:
    base = {
        "sourceRef": "file:///tmp/example",
        "manifest": _manifest(),
        "artifacts": [],
        "evidence": [],
        "contentHash": "sha256:" + "c" * 64,
        "signature": None,
        "loadedAt": datetime.now(UTC),
    }
    with pytest.raises(ValidationError, match="must use bundle://"):
        LoadedBundle.model_validate(base)

    duplicate_artifacts = deepcopy(base)
    duplicate_artifacts["sourceRef"] = "bundle://fixtures/example"
    duplicate_artifacts["artifacts"] = [_artifact(), _artifact()]
    with pytest.raises(ValidationError, match="artifact paths must be unique"):
        LoadedBundle.model_validate(duplicate_artifacts)

    duplicate_evidence = deepcopy(base)
    duplicate_evidence["sourceRef"] = "bundle://fixtures/example"
    duplicate_evidence["evidence"] = [_evidence(), _evidence()]
    with pytest.raises(ValidationError, match="evidence entries must be unique"):
        LoadedBundle.model_validate(duplicate_evidence)


def test_evidence_lifecycle_and_time_contract_fail_closed() -> None:
    with pytest.raises(ValidationError, match="requires revokedAt"):
        _evidence(status="revoked", revokedAt=None)
    with pytest.raises(ValidationError, match="only valid for revoked"):
        _evidence(revokedAt=datetime.now(UTC))
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="must be after"):
        _evidence(observedAt=now, expiresAt=now - timedelta(seconds=1))
    with pytest.raises(ValidationError, match="include a timezone"):
        _evidence(observedAt=datetime.now(UTC).replace(tzinfo=None))


def test_status_and_evidence_enums_are_closed() -> None:
    assert {item.value for item in BundleVersionStatus} == {
        "draft",
        "validated",
        "published",
        "deprecated",
        "revoked",
        "rejected",
    }
    assert {item.value for item in BundleEvidenceStatus} == {
        "pending",
        "valid",
        "invalid",
        "expired",
        "revoked",
    }
    assert {
        "manifest_validation",
        "content_hash",
        "signature_verification",
        "sbom",
        "bundle_evals",
    }.issubset({item.value for item in BundleEvidenceType})


def test_error_codes_and_http_statuses_match_the_frozen_contract() -> None:
    expected = {
        "MANIFEST_INVALID": 400,
        "VERSION_INVALID": 400,
        "SIGNATURE_INVALID": 400,
        "TRUST_ROOT_UNAVAILABLE": 503,
        "BUNDLE_VERSION_IMMUTABLE": 409,
        "DEPENDENCY_CONFLICT": 409,
        "DEPENDENCY_CYCLE": 409,
        "REVISION_CONFLICT": 409,
        "IDEMPOTENCY_CONFLICT": 409,
        "APPROVAL_STALE": 409,
        "DUTY_SEPARATION_REQUIRED": 403,
        "PREFLIGHT_FAILED": 422,
        "VERIFICATION_FAILED": 422,
        "ROLLBACK_BLOCKED": 409,
        "NOT_FOUND": 404,
    }
    assert {
        code.value: status for code, status in ERROR_HTTP_STATUS.items()
    } == expected
    error = ManifestInvalidError(
        "manifest failed validation", details={"field": "kind"}
    )
    assert error.code == AssetRegistryErrorCode.MANIFEST_INVALID
    assert error.http_status == 400
    assert error.details == {"field": "kind"}
    assert AssetNotFoundError().http_status == 404


def test_shared_json_schema_has_the_same_closed_top_level_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["apiVersion", "kind", "metadata", "spec"]
    assert set(schema["properties"]) == {
        "apiVersion",
        "kind",
        "metadata",
        "spec",
    }
    assert set(schema["$defs"]["bundleKind"]["enum"]) == {
        item.value for item in BundleKind
    }
    assert schema["$defs"]["metadata"]["additionalProperties"] is False
    assert schema["$defs"]["spec"]["additionalProperties"] is False
    assert schema["$defs"]["spec"]["required"] == [
        "platformApi",
        "dependencies",
        "optionalDependencies",
        "conflicts",
        "exports",
        "capabilities",
        "permissions",
        "migrations",
        "preflight",
        "regression",
        "rollback",
    ]
    assert "contributions" not in schema["$defs"]["spec"]["required"]
    assert schema["$defs"]["contributions"]["default"] == []
    assert len(schema["$defs"]["contributions"]["items"]["oneOf"]) == 3
    for name in (
        "apiContribution",
        "navigationContribution",
        "uiContribution",
    ):
        assert schema["$defs"][name]["additionalProperties"] is False
    assert "contributions" in schema["$defs"]["spec"]["properties"]
    generated = BundleManifest.model_json_schema(by_alias=True)
    assert set(generated["properties"]) == set(schema["properties"])


def test_owned_contract_files_contain_no_domain_specific_terms() -> None:
    owned = [
        REPO_ROOT / "services/aos-api/aos_api/asset_registry/__init__.py",
        REPO_ROOT / "services/aos-api/aos_api/asset_registry/contracts.py",
        REPO_ROOT / "services/aos-api/aos_api/asset_registry/errors.py",
        SCHEMA_PATH,
    ]
    forbidden = ("ecom" + "merce", "niu" + "shop")
    for path in owned:
        content = path.read_text(encoding="utf-8").lower()
        assert all(term not in content for term in forbidden), path
