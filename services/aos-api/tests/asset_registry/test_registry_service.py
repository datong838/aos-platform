from __future__ import annotations

import base64
import inspect
from collections.abc import Callable, Collection
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.contracts import (
    BundleEvidenceStatus,
    BundleEvidenceType,
    BundleKind,
    BundleManifest,
    BundleSignature,
    BundleVersionStatus,
    LoadedBundle,
)
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    AssetRegistryError,
    AssetRegistryErrorCode,
    BundleVersionImmutableError,
)
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.signature import TrustRoot

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)
SOURCE_REF = "bundle://fixtures/solution-example"
CREATE_ROLES = {"developer"}
PUBLISH_ROLES = {"asset-publisher"}
PUBLISHER_SCOPES = {"aos"}
KEY_ID = "release-2026-01"
ROOT_REVISION = "sha256:" + "1" * 64
ROOT_NOT_AFTER = NOW + timedelta(days=1)


class MutableTrustRoots:
    def __init__(self, root: TrustRoot) -> None:
        self.root = root
        self.failure: Exception | None = None

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        if self.failure is not None:
            raise self.failure
        if self.root.publisher == publisher and self.root.key_id == key_id:
            return self.root
        return None


class RuntimeSigner:
    def __init__(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        public_key = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.trust_roots = MutableTrustRoots(
            TrustRoot(
                publisher="aos",
                key_id=KEY_ID,
                public_key=public_key,
                revision=ROOT_REVISION,
                not_before=NOW - timedelta(days=1),
                not_after=ROOT_NOT_AFTER,
            )
        )

    def prepare(self, loaded: LoadedBundle) -> LoadedBundle:
        payload = loaded.model_dump(mode="python", by_alias=True)
        descriptor = {
            "manifest": loaded.manifest.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=False,
            ),
            "artifacts": [
                item.model_dump(mode="json", by_alias=True) for item in loaded.artifacts
            ],
        }
        content_hash = canonical_sha256(descriptor)
        evidence = payload["evidence"]
        for item in evidence:
            if item["type"] == BundleEvidenceType.CONTENT_HASH.value:
                item["artifactHash"] = content_hash
            if item["type"] == BundleEvidenceType.SIGNATURE_VERIFICATION.value:
                item["expiresAt"] = ROOT_NOT_AFTER
                item["metadata"] = {
                    **item.get("metadata", {}),
                    "trustRootRevision": ROOT_REVISION,
                }
        payload["contentHash"] = content_hash
        if loaded.signature is not None:
            payload["signature"] = {
                "algorithm": "Ed25519",
                "keyId": KEY_ID,
                "signature": base64.b64encode(
                    self.private_key.sign(canonical_json(descriptor))
                ).decode("ascii"),
                "signedAt": NOW,
            }
            signature_hash = canonical_sha256(
                BundleSignature.model_validate(payload["signature"]).model_dump(
                    mode="json", by_alias=True, exclude_none=False
                )
            )
            next(
                item
                for item in evidence
                if item["type"] == BundleEvidenceType.SIGNATURE_VERIFICATION.value
            )["artifactHash"] = signature_hash
        return LoadedBundle.model_validate(payload)


class FakeLoader:
    def __init__(self, loaded: LoadedBundle, signer: RuntimeSigner) -> None:
        self._signer = signer
        self._loaded = signer.prepare(loaded)
        self.calls: list[str] = []

    @property
    def trust_roots(self) -> MutableTrustRoots:
        return self._signer.trust_roots

    @property
    def loaded(self) -> LoadedBundle:
        return self._loaded

    @loaded.setter
    def loaded(self, value: LoadedBundle) -> None:
        self._loaded = self._signer.prepare(value)

    def load(self, source_ref: str) -> LoadedBundle:
        self.calls.append(source_ref)
        return self.loaded


class FakeStore:
    def __init__(self) -> None:
        self.bundles: dict[tuple[str, str], dict[str, Any]] = {}
        self.versions: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.transitions: list[
            tuple[str, str, tuple[str, ...], str, str, str | None, str]
        ] = []

    def list_bundles(self) -> list[dict[str, Any]]:
        return [
            deepcopy({key: value for key, value in item.items() if key != "versions"})
            for item in self.bundles.values()
        ]

    def create_bundle(
        self,
        publisher: str,
        bundle_id: str,
        kind: BundleKind | str,
        display_name: str,
        created_by: str,
    ) -> dict[str, Any]:
        key = (publisher, bundle_id)
        record = {
            "publisher": publisher,
            "bundleId": bundle_id,
            "kind": kind.value if isinstance(kind, BundleKind) else kind,
            "displayName": display_name,
            "createdAt": NOW.isoformat(),
            "versions": [],
        }
        self.bundles[key] = record
        return deepcopy(
            {key: value for key, value in record.items() if key != "versions"}
        )

    def get_bundle(
        self,
        bundle_id: str,
        publisher: str | None = None,
    ) -> dict[str, Any]:
        matches = [
            value
            for (candidate_publisher, candidate_id), value in self.bundles.items()
            if candidate_id == bundle_id
            and (publisher is None or candidate_publisher == publisher)
        ]
        if len(matches) != 1:
            raise AssetNotFoundError()
        return deepcopy(matches[0])

    def create_version(
        self,
        loaded_bundle: LoadedBundle,
        created_by: str,
    ) -> dict[str, Any]:
        manifest = loaded_bundle.manifest
        key = (
            manifest.metadata.publisher,
            manifest.metadata.id,
            manifest.metadata.version,
        )
        record = {
            "publisher": manifest.metadata.publisher,
            "bundleId": manifest.metadata.id,
            "kind": manifest.kind.value,
            "displayName": manifest.metadata.display_name,
            "version": manifest.metadata.version,
            "manifest": manifest.model_dump(mode="json", by_alias=True),
            "contentHash": loaded_bundle.content_hash,
            "signature": (
                loaded_bundle.signature.model_dump(mode="json", by_alias=True)
                if loaded_bundle.signature is not None
                else None
            ),
            "status": BundleVersionStatus.DRAFT.value,
            "createdBy": created_by,
            "createdAt": NOW.isoformat(),
            "updatedAt": NOW.isoformat(),
            "dependencies": [],
            "artifacts": [
                item.model_dump(mode="json", by_alias=True)
                for item in loaded_bundle.artifacts
            ],
            "evidence": [
                item.model_dump(mode="json", by_alias=True)
                for item in loaded_bundle.evidence
            ],
            "lifecycleEvents": [],
        }
        self.versions[key] = record
        self.bundles[(key[0], key[1])]["versions"].append(
            {
                field: record[field]
                for field in (
                    "version",
                    "contentHash",
                    "signature",
                    "status",
                    "createdBy",
                    "createdAt",
                    "updatedAt",
                )
            }
        )
        return deepcopy(record)

    def get_version(
        self,
        bundle_id: str,
        version: str,
        publisher: str | None = None,
    ) -> dict[str, Any]:
        matches = [
            value
            for (
                candidate_publisher,
                candidate_id,
                candidate_version,
            ), value in self.versions.items()
            if candidate_id == bundle_id
            and candidate_version == version
            and (publisher is None or candidate_publisher == publisher)
        ]
        if len(matches) != 1:
            raise AssetNotFoundError()
        return deepcopy(matches[0])

    def transition_version(
        self,
        bundle_id: str,
        version: str,
        expected_statuses: Collection[BundleVersionStatus | str],
        target_status: BundleVersionStatus | str,
        actor: str,
        reason: str | None = None,
        *,
        publisher: str | None = None,
        precondition: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        record = self.get_version(bundle_id, version, publisher)
        expected = tuple(
            item.value if isinstance(item, BundleVersionStatus) else item
            for item in expected_statuses
        )
        target = (
            target_status.value
            if isinstance(target_status, BundleVersionStatus)
            else target_status
        )
        if record["status"] not in expected:
            raise BundleVersionImmutableError("fake store rejected transition")
        if precondition is not None:
            precondition(record)
        key = (record["publisher"], bundle_id, version)
        self.versions[key]["status"] = target
        self.versions[key]["updatedAt"] = NOW.isoformat()
        self.versions[key]["lifecycleEvents"].append(
            {
                "sequence": len(record["lifecycleEvents"]) + 1,
                "fromStatus": record["status"],
                "toStatus": target,
                "actor": actor,
                "reason": reason,
                "evidenceRevision": canonical_sha256(record["evidence"]),
                "evidenceSnapshot": deepcopy(record["evidence"]),
                "createdAt": NOW.isoformat(),
            }
        )
        self.transitions.append(
            (bundle_id, version, expected, target, actor, reason, record["publisher"])
        )
        return deepcopy(self.versions[key])


class MutableClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _manifest(**updates: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
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
                {"id": "plugin.search", "version": ">=2.0.0 <3.0.0"}
            ],
            "conflicts": [{"id": "solution.legacy", "version": "<1.5.0"}],
            "exports": {},
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migrations": {
                "plan": None,
                "downgradePolicy": "retain-canonical",
            },
            "preflight": None,
            "regression": None,
            "rollback": None,
        },
    }
    for path, value in updates.items():
        if path.startswith("metadata_"):
            payload["metadata"][path.removeprefix("metadata_")] = value
        elif path.startswith("spec_"):
            payload["spec"][path.removeprefix("spec_")] = value
        else:
            payload[path] = value
    return payload


HASH = canonical_sha256(
    {
        "manifest": BundleManifest.model_validate(_manifest()).model_dump(
            mode="json",
            by_alias=True,
            exclude_none=False,
        ),
        "artifacts": [],
    }
)


def _evidence(
    evidence_type: BundleEvidenceType,
    *,
    status: BundleEvidenceStatus = BundleEvidenceStatus.VALID,
    observed_at: datetime = NOW - timedelta(hours=1),
    expires_at: datetime | None = NOW + timedelta(days=1),
    revoked_at: datetime | None = None,
) -> dict[str, Any]:
    artifact_hash = (
        HASH
        if evidence_type == BundleEvidenceType.CONTENT_HASH
        else "sha256:" + evidence_type.value.encode().hex()[:8].ljust(64, "b")
    )
    return {
        "type": evidence_type.value,
        "artifactRef": f"bundle://fixtures/solution-example/evidence/{evidence_type.value}.json",
        "artifactHash": artifact_hash,
        "status": status.value,
        "observedAt": observed_at,
        "expiresAt": expires_at,
        "revokedAt": revoked_at,
        "metadata": {
            "serverDerived": True,
            **(
                {"trustRootRevision": ROOT_REVISION}
                if evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION
                else {}
            ),
        },
    }


def _loaded_bundle(
    *,
    manifest: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    signed: bool = True,
) -> LoadedBundle:
    signature_payload = (
        {
            "algorithm": "Ed25519",
            "keyId": KEY_ID,
            "signature": base64.b64encode(b"0" * 64).decode("ascii"),
            "signedAt": NOW,
        }
        if signed
        else None
    )
    evidence_payload = evidence
    if evidence_payload is None:
        evidence_payload = [
            _evidence(evidence_type)
            for evidence_type in (
                BundleEvidenceType.MANIFEST_VALIDATION,
                BundleEvidenceType.CONTENT_HASH,
                BundleEvidenceType.SIGNATURE_VERIFICATION,
                BundleEvidenceType.SBOM,
                BundleEvidenceType.BUNDLE_EVALS,
            )
        ]
        if signature_payload is not None:
            signature_hash = canonical_sha256(
                BundleSignature.model_validate(signature_payload).model_dump(
                    mode="json", by_alias=True, exclude_none=False
                )
            )
            next(
                item
                for item in evidence_payload
                if item["type"] == BundleEvidenceType.SIGNATURE_VERIFICATION.value
            )["artifactHash"] = signature_hash
    return LoadedBundle.model_validate(
        {
            "sourceRef": SOURCE_REF,
            "manifest": manifest or _manifest(),
            "artifacts": [],
            "evidence": evidence_payload,
            "contentHash": HASH,
            "signature": signature_payload,
            "loadedAt": NOW,
        }
    )


def _service(
    loaded: LoadedBundle | None = None,
) -> tuple[RegistryService, FakeStore, FakeLoader, MutableClock]:
    store = FakeStore()
    signer = RuntimeSigner()
    loader = FakeLoader(loaded or _loaded_bundle(), signer)
    clock = MutableClock()
    service = RegistryService(
        store=store,
        loader=loader,
        clock=clock,
        trust_roots=loader.trust_roots,
    )
    return service, store, loader, clock


def _create_bundle_and_version(
    service: RegistryService,
    *,
    roles: set[str] = CREATE_ROLES,
) -> dict[str, Any]:
    service.create_bundle(
        publisher="aos",
        bundle_id="solution.example",
        kind="SolutionPack",
        display_name="Example",
        actor="author-1",
        roles=roles,
        publisher_scopes=PUBLISHER_SCOPES,
    )
    return service.create_version(
        bundle_id="solution.example",
        source_ref=SOURCE_REF,
        actor="author-1",
        roles=roles,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )


def test_catalog_create_list_and_get_use_the_fixed_store_contract() -> None:
    service, _, _, _ = _service()

    created = service.create_bundle(
        publisher="aos",
        bundle_id="solution.example",
        kind=BundleKind.SOLUTION_PACK,
        display_name="Example",
        actor="author-1",
        roles={"developer"},
        publisher_scopes=PUBLISHER_SCOPES,
    )

    assert created["bundleId"] == "solution.example"
    assert service.list_bundles() == [created]
    assert (
        service.get_bundle(bundle_id="solution.example", publisher="aos")["publisher"]
        == "aos"
    )


@pytest.mark.parametrize("role", ["developer", "admin", "asset-publisher"])
def test_all_frozen_draft_create_roles_are_allowed(role: str) -> None:
    service, _, _, _ = _service()

    created = service.create_bundle(
        publisher="aos",
        bundle_id="solution.example",
        kind="SolutionPack",
        display_name="Example",
        actor="author-1",
        roles={role},
        publisher_scopes=PUBLISHER_SCOPES,
    )

    assert created["bundleId"] == "solution.example"


@pytest.mark.parametrize("role", ["viewer", "asset-reader", ""])
def test_create_requires_an_explicit_allowed_role(role: str) -> None:
    service, _, _, _ = _service()

    with pytest.raises(AssetRegistryError) as caught:
        service.create_bundle(
            publisher="aos",
            bundle_id="solution.example",
            kind="SolutionPack",
            display_name="Example",
            actor="author-1",
            roles={role},
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == AssetRegistryErrorCode.DUTY_SEPARATION_REQUIRED


def test_create_version_uses_only_the_loader_derived_snapshot() -> None:
    service, _, loader, _ = _service()

    created = _create_bundle_and_version(service)

    assert loader.calls == [SOURCE_REF]
    assert created["contentHash"] == HASH
    assert created["status"] == "draft"
    parameters = inspect.signature(service.create_version).parameters
    assert "content_hash" not in parameters
    assert "validated" not in parameters


def test_unsigned_loader_result_can_only_be_created_as_draft() -> None:
    service, _, _, _ = _service(_loaded_bundle(signed=False, evidence=[]))

    created = _create_bundle_and_version(service)

    assert created["status"] == "draft"
    with pytest.raises(AssetRegistryError) as caught:
        service.validate(
            bundle_id="solution.example",
            version="1.0.0",
            actor="author-1",
            roles=CREATE_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )
    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID


@pytest.mark.parametrize(
    ("manifest_update", "value"),
    [
        ("metadata_id", "solution.other"),
        ("metadata_publisher", "other"),
        ("metadata_displayName", "Other"),
        ("kind", "DomainPack"),
    ],
)
def test_create_version_rejects_manifest_target_mismatch(
    manifest_update: str,
    value: str,
) -> None:
    loaded = _loaded_bundle(manifest=_manifest(**{manifest_update: value}))
    service, _, _, _ = _service(loaded)
    service.create_bundle(
        publisher="aos",
        bundle_id="solution.example",
        kind="SolutionPack",
        display_name="Example",
        actor="author-1",
        roles=CREATE_ROLES,
        publisher_scopes=PUBLISHER_SCOPES,
    )

    with pytest.raises(AssetRegistryError) as caught:
        service.create_version(
            bundle_id="solution.example",
            source_ref=SOURCE_REF,
            actor="author-1",
            roles=CREATE_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID


@pytest.mark.parametrize(
    ("manifest_update", "expected_field"),
    [
        ("metadata_version", "metadata.version"),
        ("spec_platformApi", "spec.platformApi"),
        (
            "spec_dependencies",
            "spec.dependencies[0].version",
        ),
        (
            "spec_optionalDependencies",
            "spec.optionalDependencies[0].version",
        ),
        ("spec_conflicts", "spec.conflicts[0].version"),
    ],
)
def test_create_version_rejects_invalid_semver_and_ranges(
    manifest_update: str,
    expected_field: str,
) -> None:
    value: object = "not-semver"
    if manifest_update == "spec_dependencies":
        value = [{"id": "domain.foundation", "version": "not-semver"}]
    elif manifest_update == "spec_optionalDependencies":
        value = [{"id": "plugin.search", "version": "not-semver"}]
    elif manifest_update == "spec_conflicts":
        value = [{"id": "solution.legacy", "version": "not-semver"}]
    service, _, _, _ = _service(
        _loaded_bundle(manifest=_manifest(**{manifest_update: value}))
    )
    service.create_bundle(
        publisher="aos",
        bundle_id="solution.example",
        kind="SolutionPack",
        display_name="Example",
        actor="author-1",
        roles=CREATE_ROLES,
        publisher_scopes=PUBLISHER_SCOPES,
    )

    with pytest.raises(AssetRegistryError) as caught:
        service.create_version(
            bundle_id="solution.example",
            source_ref=SOURCE_REF,
            actor="author-1",
            roles=CREATE_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == AssetRegistryErrorCode.VERSION_INVALID
    assert caught.value.details == {"field": expected_field}


def test_validate_uses_persisted_server_snapshot_without_reloading() -> None:
    service, store, loader, _ = _service()
    _create_bundle_and_version(service)

    validated = service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="author-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )

    assert validated["status"] == "validated"
    assert loader.calls == [SOURCE_REF]
    assert store.transitions[-1][2:4] == (("draft",), "validated")
    assert store.transitions[-1][-1] == "aos"


def test_actions_use_publisher_to_disambiguate_same_bundle_id_and_version() -> None:
    service, store, loader, _ = _service()
    _create_bundle_and_version(service)
    service.create_bundle(
        publisher="other",
        bundle_id="solution.example",
        kind="SolutionPack",
        display_name="Example",
        actor="other-author",
        roles=CREATE_ROLES,
        publisher_scopes={"other"},
    )
    loader.loaded = _loaded_bundle(manifest=_manifest(metadata_publisher="other"))
    service.create_version(
        bundle_id="solution.example",
        source_ref=SOURCE_REF,
        actor="other-author",
        roles=CREATE_ROLES,
        publisher="other",
        publisher_scopes={"other"},
    )

    with pytest.raises(AssetRegistryError) as caught:
        service.validate(
            bundle_id="solution.example",
            version="1.0.0",
            actor="author-1",
            roles=CREATE_ROLES,
        )
    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID

    validated = service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        publisher="aos",
        actor="author-1",
        roles=CREATE_ROLES,
        publisher_scopes=PUBLISHER_SCOPES,
    )

    assert validated["publisher"] == "aos"
    assert validated["status"] == "validated"
    assert store.get_version("solution.example", "1.0.0", "other")["status"] == "draft"


@pytest.mark.parametrize(
    ("evidence_type", "change", "expected_code"),
    [
        (
            BundleEvidenceType.MANIFEST_VALIDATION,
            "missing",
            AssetRegistryErrorCode.MANIFEST_INVALID,
        ),
        (
            BundleEvidenceType.CONTENT_HASH,
            "expired",
            AssetRegistryErrorCode.MANIFEST_INVALID,
        ),
        (
            BundleEvidenceType.SIGNATURE_VERIFICATION,
            "invalid",
            AssetRegistryErrorCode.SIGNATURE_INVALID,
        ),
        (
            BundleEvidenceType.SBOM,
            "revoked",
            AssetRegistryErrorCode.VERIFICATION_FAILED,
        ),
        (
            BundleEvidenceType.BUNDLE_EVALS,
            "future",
            AssetRegistryErrorCode.VERIFICATION_FAILED,
        ),
    ],
)
def test_validate_fails_closed_for_missing_invalid_or_stale_evidence(
    evidence_type: BundleEvidenceType,
    change: str,
    expected_code: AssetRegistryErrorCode,
) -> None:
    evidence = [
        _evidence(item)
        for item in (
            BundleEvidenceType.MANIFEST_VALIDATION,
            BundleEvidenceType.CONTENT_HASH,
            BundleEvidenceType.SIGNATURE_VERIFICATION,
            BundleEvidenceType.SBOM,
            BundleEvidenceType.BUNDLE_EVALS,
        )
        if not (item == evidence_type and change == "missing")
    ]
    for item in evidence:
        if item["type"] != evidence_type.value:
            continue
        if change == "expired":
            item["expiresAt"] = NOW
        elif change == "invalid":
            item["status"] = "invalid"
        elif change == "revoked":
            item["status"] = "revoked"
            item["revokedAt"] = NOW
        elif change == "future":
            item["observedAt"] = NOW + timedelta(seconds=1)
            item["expiresAt"] = NOW + timedelta(days=1)

    service, store, _, _ = _service(_loaded_bundle(evidence=evidence))
    _create_bundle_and_version(service)

    with pytest.raises(AssetRegistryError) as caught:
        service.validate(
            bundle_id="solution.example",
            version="1.0.0",
            actor="author-1",
            roles=CREATE_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == expected_code
    assert store.get_version("solution.example", "1.0.0")["status"] == "draft"


def test_validate_rejects_a_tampered_persisted_snapshot() -> None:
    service, store, _, _ = _service()
    _create_bundle_and_version(service)
    key = ("aos", "solution.example", "1.0.0")
    store.versions[key]["manifest"]["metadata"]["id"] = "solution.other"

    with pytest.raises(AssetRegistryError) as caught:
        service.validate(
            bundle_id="solution.example",
            version="1.0.0",
            actor="author-1",
            roles=CREATE_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID
    assert store.transitions == []


def test_validate_binds_content_hash_to_its_server_evidence() -> None:
    service, store, _, _ = _service()
    _create_bundle_and_version(service)
    key = ("aos", "solution.example", "1.0.0")
    store.versions[key]["contentHash"] = "sha256:" + "f" * 64

    with pytest.raises(AssetRegistryError) as caught:
        service.validate(
            bundle_id="solution.example",
            version="1.0.0",
            actor="author-1",
            roles=CREATE_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID
    assert caught.value.details == {"evidenceType": "content_hash"}
    assert store.transitions == []


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("signature", {"algorithm": "RSA"}, AssetRegistryErrorCode.SIGNATURE_INVALID),
        ("evidence", [{"status": "valid"}], AssetRegistryErrorCode.VERIFICATION_FAILED),
    ],
)
def test_validate_maps_corrupt_security_records_to_stable_errors(
    field: str,
    value: object,
    expected_code: AssetRegistryErrorCode,
) -> None:
    service, store, _, _ = _service()
    _create_bundle_and_version(service)
    key = ("aos", "solution.example", "1.0.0")
    store.versions[key][field] = value

    with pytest.raises(AssetRegistryError) as caught:
        service.validate(
            bundle_id="solution.example",
            version="1.0.0",
            actor="author-1",
            roles=CREATE_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == expected_code
    assert store.transitions == []


@pytest.mark.parametrize("role", ["admin", "asset-publisher"])
def test_both_frozen_publish_roles_are_allowed(role: str) -> None:
    service, _, _, _ = _service()
    _create_bundle_and_version(service)
    service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="author-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )

    published = service.publish(
        bundle_id="solution.example",
        version="1.0.0",
        actor="publisher-1",
        roles={role},
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )

    assert published["status"] == "published"


def test_publish_rechecks_role_and_evidence_expiry() -> None:
    service, store, _, clock = _service()
    _create_bundle_and_version(service)
    service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="author-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )

    with pytest.raises(AssetRegistryError) as caught:
        service.publish(
            bundle_id="solution.example",
            version="1.0.0",
            actor="author-1",
            roles={"developer"},
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )
    assert caught.value.code == AssetRegistryErrorCode.DUTY_SEPARATION_REQUIRED

    clock.now = NOW + timedelta(days=2)
    with pytest.raises(AssetRegistryError) as caught:
        service.publish(
            bundle_id="solution.example",
            version="1.0.0",
            actor="publisher-1",
            roles=PUBLISH_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )
    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID
    assert store.get_version("solution.example", "1.0.0")["status"] == "validated"


def test_publish_deprecate_and_revoke_follow_the_frozen_state_machine() -> None:
    service, store, loader, _ = _service()
    _create_bundle_and_version(service)
    service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="author-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    published = service.publish(
        bundle_id="solution.example",
        version="1.0.0",
        actor="publisher-1",
        roles=PUBLISH_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    assert published["status"] == "published"

    deprecated = service.deprecate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="publisher-1",
        roles=PUBLISH_ROLES,
        reason="superseded by 2.0.0",
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    assert deprecated["status"] == "deprecated"
    assert store.transitions[-1][-2] == "superseded by 2.0.0"

    second_loaded = _loaded_bundle(manifest=_manifest(metadata_version="2.0.0"))
    loader.loaded = second_loaded
    service.create_version(
        bundle_id="solution.example",
        source_ref=SOURCE_REF,
        actor="author-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    service.validate(
        bundle_id="solution.example",
        version="2.0.0",
        actor="author-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    service.publish(
        bundle_id="solution.example",
        version="2.0.0",
        actor="publisher-1",
        roles=PUBLISH_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    revoked = service.revoke(
        bundle_id="solution.example",
        version="2.0.0",
        actor="publisher-1",
        roles=PUBLISH_ROLES,
        reason="publisher trust root revoked",
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    assert revoked["status"] == "revoked"


def test_illegal_state_transitions_fail_closed_with_stable_error() -> None:
    service, _, _, _ = _service()
    _create_bundle_and_version(service)

    with pytest.raises(AssetRegistryError) as caught:
        service.publish(
            bundle_id="solution.example",
            version="1.0.0",
            actor="publisher-1",
            roles=PUBLISH_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )
    assert caught.value.code == AssetRegistryErrorCode.BUNDLE_VERSION_IMMUTABLE

    for action in (service.deprecate, service.revoke):
        with pytest.raises(AssetRegistryError) as caught:
            action(
                bundle_id="solution.example",
                version="1.0.0",
                actor="publisher-1",
                roles=PUBLISH_ROLES,
                reason="terminal transition requested",
                publisher="aos",
                publisher_scopes=PUBLISHER_SCOPES,
            )
        assert caught.value.code == AssetRegistryErrorCode.BUNDLE_VERSION_IMMUTABLE


@pytest.mark.parametrize(
    "operation",
    ("create_bundle", "create_version", "validate", "publish", "deprecate", "revoke"),
)
def test_every_write_rejects_cross_publisher_scope(operation: str) -> None:
    service, _, _, _ = _service()
    common = {
        "bundle_id": "solution.example",
        "actor": "actor-1",
        "roles": {"asset-publisher", "developer"},
        "publisher_scopes": PUBLISHER_SCOPES,
    }

    with pytest.raises(AssetRegistryError) as caught:
        if operation == "create_bundle":
            service.create_bundle(
                **common,
                publisher="other",
                kind="SolutionPack",
                display_name="Example",
            )
        elif operation == "create_version":
            service.create_version(
                **common,
                publisher="other",
                source_ref=SOURCE_REF,
            )
        else:
            action = getattr(service, operation)
            action(
                **common,
                publisher="other",
                version="1.0.0",
                **(
                    {"reason": "security transition"}
                    if operation in {"deprecate", "revoke"}
                    else {}
                ),
            )

    assert caught.value.code == AssetRegistryErrorCode.DUTY_SEPARATION_REQUIRED
    assert caught.value.http_status == 403


def test_admin_wildcard_does_not_expand_scope_but_registry_admin_wildcard_does() -> (
    None
):
    service, _, _, _ = _service()

    with pytest.raises(AssetRegistryError) as caught:
        service.create_bundle(
            publisher="aos",
            bundle_id="solution.example",
            kind="SolutionPack",
            display_name="Example",
            actor="admin-1",
            roles={"admin"},
            publisher_scopes={"*"},
        )
    assert caught.value.code == AssetRegistryErrorCode.DUTY_SEPARATION_REQUIRED

    created = service.create_bundle(
        publisher="aos",
        bundle_id="solution.example",
        kind="SolutionPack",
        display_name="Example",
        actor="registry-admin-1",
        roles={"asset-registry-admin"},
        publisher_scopes={"*"},
    )
    assert created["publisher"] == "aos"


@pytest.mark.parametrize(
    "operation",
    ("create_version", "validate", "publish", "deprecate", "revoke"),
)
def test_version_writes_require_an_explicit_publisher(operation: str) -> None:
    service, _, _, _ = _service()
    common = {
        "bundle_id": "solution.example",
        "actor": "actor-1",
        "roles": {"asset-publisher", "developer"},
        "publisher_scopes": PUBLISHER_SCOPES,
    }

    with pytest.raises(AssetRegistryError) as caught:
        if operation == "create_version":
            service.create_version(**common, source_ref=SOURCE_REF)
        else:
            getattr(service, operation)(
                **common,
                version="1.0.0",
                **(
                    {"reason": "security transition"}
                    if operation in {"deprecate", "revoke"}
                    else {}
                ),
            )

    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID


@pytest.mark.parametrize("operation", ("deprecate", "revoke"))
@pytest.mark.parametrize("reason", (None, "", "  "))
def test_terminal_writes_require_a_normalized_reason(
    operation: str,
    reason: str | None,
) -> None:
    service, _, _, _ = _service()

    with pytest.raises(AssetRegistryError) as caught:
        getattr(service, operation)(
            bundle_id="solution.example",
            version="1.0.0",
            actor="publisher-1",
            roles=PUBLISH_ROLES,
            reason=reason,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID


def test_publish_enforces_creator_validator_separation_and_lifecycle_history() -> None:
    service, store, _, _ = _service()
    _create_bundle_and_version(service)
    validated = service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="validator-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    assert validated["lifecycleEvents"] == [
        {
            "sequence": 1,
            "fromStatus": "draft",
            "toStatus": "validated",
            "actor": "validator-1",
            "reason": None,
            "evidenceRevision": canonical_sha256(validated["evidence"]),
            "evidenceSnapshot": validated["evidence"],
            "createdAt": NOW.isoformat(),
        }
    ]

    for actor in ("author-1", "validator-1"):
        with pytest.raises(AssetRegistryError) as caught:
            service.publish(
                bundle_id="solution.example",
                version="1.0.0",
                actor=actor,
                roles=PUBLISH_ROLES,
                publisher="aos",
                publisher_scopes=PUBLISHER_SCOPES,
            )
        assert caught.value.code == AssetRegistryErrorCode.DUTY_SEPARATION_REQUIRED
        assert store.get_version("solution.example", "1.0.0", "aos")["status"] == (
            "validated"
        )

    published = service.publish(
        bundle_id="solution.example",
        version="1.0.0",
        actor="publisher-2",
        roles=PUBLISH_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    assert published["status"] == "published"
    assert [item["actor"] for item in published["lifecycleEvents"]] == [
        "validator-1",
        "publisher-2",
    ]


@pytest.mark.parametrize("trust_change", ("revoke", "revision"))
def test_publish_rechecks_the_current_trust_root_after_validation(
    trust_change: str,
) -> None:
    service, store, loader, _ = _service()
    _create_bundle_and_version(service)
    service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="validator-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    root = loader.trust_roots.root
    loader.trust_roots.root = replace(
        root,
        **(
            {"revoked_at": NOW}
            if trust_change == "revoke"
            else {"revision": "sha256:" + "2" * 64}
        ),
    )

    with pytest.raises(AssetRegistryError) as caught:
        service.publish(
            bundle_id="solution.example",
            version="1.0.0",
            actor="publisher-2",
            roles=PUBLISH_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID
    assert store.get_version("solution.example", "1.0.0", "aos")["status"] == (
        "validated"
    )


def test_trust_root_provider_outage_returns_retryable_503_without_state_change() -> (
    None
):
    service, store, loader, _ = _service()
    _create_bundle_and_version(service)
    service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="validator-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    before = store.get_version("solution.example", "1.0.0", "aos")
    loader.trust_roots.failure = RuntimeError(
        "trust roots at /secret/path contain token=do-not-leak"
    )

    with pytest.raises(AssetRegistryError) as caught:
        service.publish(
            bundle_id="solution.example",
            version="1.0.0",
            actor="publisher-2",
            roles=PUBLISH_ROLES,
            publisher="aos",
            publisher_scopes=PUBLISHER_SCOPES,
        )

    assert caught.value.code == AssetRegistryErrorCode.TRUST_ROOT_UNAVAILABLE
    assert caught.value.http_status == 503
    assert caught.value.details == {"retryable": True}
    assert "/secret/path" not in str(caught.value)
    assert store.get_version("solution.example", "1.0.0", "aos") == before


def test_public_version_projection_redacts_audit_details_without_mutating_store() -> (
    None
):
    service, store, _, _ = _service()
    _create_bundle_and_version(service)
    service.validate(
        bundle_id="solution.example",
        version="1.0.0",
        actor="validator-1",
        roles=CREATE_ROLES,
        publisher="aos",
        publisher_scopes=PUBLISHER_SCOPES,
    )
    raw = store.get_version("solution.example", "1.0.0", "aos")

    public = service.get_version(
        bundle_id="solution.example",
        version="1.0.0",
        publisher="aos",
    )

    assert all(
        "artifactRef" not in item and "metadata" not in item
        for item in public["evidence"]
    )
    assert all(
        "actor" not in item and "reason" not in item and "evidenceSnapshot" not in item
        for item in public["lifecycleEvents"]
    )
    assert store.get_version("solution.example", "1.0.0", "aos") == raw


def test_get_version_rejects_invalid_semver_before_store_lookup() -> None:
    service, _, _, _ = _service()

    with pytest.raises(AssetRegistryError) as caught:
        service.get_version(bundle_id="solution.example", version="latest")

    assert caught.value.code == AssetRegistryErrorCode.VERSION_INVALID
