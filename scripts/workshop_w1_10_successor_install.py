"""W1-10 canonical Bundle publish and successor Installation.

The command is dry-run by default.  ``--apply`` is the only state-changing
entrypoint and all writes go through Registry/Composition/Installation services.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "services/aos-api"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from aos_api.asset_registry.canonical_json import canonical_sha256  # noqa: E402
from aos_api.asset_registry.composition_contracts import (  # noqa: E402
    ApproveInstallationRequest,
    CompositionRequest,
    CreateInstallationRequest,
    CurrentInstallationRef,
    EmptyInstallationActionRequest,
    InstallationResponse,
    StoredCompositionLock,
)
from aos_api.asset_registry.composition_service import CompositionService  # noqa: E402
from aos_api.asset_registry.composition_store import PostgresCompositionStore  # noqa: E402
from aos_api.ecommerce_workshop_catalog import (  # noqa: E402
    _effective_active_rows,
)
from aos_api.asset_registry.errors import AssetNotFoundError  # noqa: E402
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator  # noqa: E402
from aos_api.asset_registry.installation_service import InstallationService  # noqa: E402
from aos_api.asset_registry.installation_store import PostgresInstallationStore  # noqa: E402
from aos_api.asset_registry.manifest_loader import ManifestLoader, SIGNATURE_FILENAME  # noqa: E402
from aos_api.asset_registry.registry_service import RegistryService  # noqa: E402
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader  # noqa: E402
from aos_api.asset_registry.registry_store import PostgresRegistryStore  # noqa: E402
from aos_api.asset_registry.release_policy import ReleasePolicy  # noqa: E402
from aos_api.asset_registry.signature import FrozenTrustRootProvider, TrustRoot  # noqa: E402
from aos_api.db import connect  # noqa: E402


ORG_ID = "org-org"
PROJECT_ID = "dev-project"
PUBLISHER = "aos"
SOURCE_ALIAS = "d3-catalog"
RUNTIME_KEY_ID = "d3-global-signer"
RUNTIME_KEY_PATH = REPOSITORY_ROOT / "scripts/.d3_runtime_ed25519.pem"
TRUST_NOT_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
TRUST_NOT_AFTER = datetime(2036, 1, 1, tzinfo=UTC)

REGISTRY_ROLES = frozenset({"asset-publisher", "asset-registry-admin", "developer"})
PUBLISH_ROLES = frozenset({"asset-publisher", "asset-registry-admin"})
PUBLISHER_SCOPES = frozenset({PUBLISHER})
MAKER = "workshop-w1-10-successor-maker"
CHECKER = "workshop-w1-10-successor-checker"
MAKER_ROLES = frozenset({"asset-installer"})
CHECKER_ROLES = frozenset({"asset-install-approver"})
MARKINGS = frozenset()
IDEMPOTENCY_PREFIX = "workshop-w1-10-successor-20260815-v1"


class ReleaseSpec(NamedTuple):
    bundle_id: str
    version: str
    author_path: Path
    release_path: Path
    source_ref: str
    expected_module_ids: tuple[str, ...]
    expected_routes: tuple[str, ...]


class SuccessorInstallBlocked(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def release_specs(repository_root: Path = REPOSITORY_ROOT) -> tuple[ReleaseSpec, ...]:
    root = repository_root / "bundles/releases/ecommerce"
    return (
        ReleaseSpec(
            "solution.ecommerce.growth",
            "1.3.0",
            repository_root / "bundles/solutions/ecommerce-growth",
            root / "solution.ecommerce.growth/1.3.0",
            "bundle://d3-catalog/releases/ecommerce/solution.ecommerce.growth/1.3.0",
            (
                "ecommerce.task-cockpit",
                "ecommerce.content-campaign",
                "ecommerce.creator-growth",
                "ecommerce.media-studio",
                "ecommerce.analyst",
                "ecommerce.price-governance",
                "ecommerce.customer",
            ),
            (
                "/workshop/cockpit",
                "/workshop/content-campaign",
                "/workshop/creator-growth",
                "/workshop/media-studio",
                "/workshop/analyst",
                "/workshop/price-governance",
                "/workshop/customer",
            ),
        ),
        ReleaseSpec(
            "solution.ecommerce.operations-base",
            "1.1.0",
            repository_root / "bundles/solutions/ecommerce-operations-base",
            root / "solution.ecommerce.operations-base/1.1.0",
            "bundle://d3-catalog/releases/ecommerce/solution.ecommerce.operations-base/1.1.0",
            ("ecommerce.operations",),
            ("/workshop/operations",),
        ),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="execute canonical writes")
    parser.add_argument("--output", type=Path, help="write a non-secret JSON receipt")
    return parser.parse_args(argv)


def _tree(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        raise SuccessorInstallBlocked("RELEASE_SNAPSHOT_MISSING", str(root))
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != SIGNATURE_FILENAME
    }


def validate_release_snapshots(specs: Sequence[ReleaseSpec]) -> dict[str, Any]:
    unsigned = ManifestLoader({SOURCE_ALIAS: REPOSITORY_ROOT / "bundles"})
    seen_ids: set[str] = set()
    seen_routes: set[str] = set()
    result: list[dict[str, Any]] = []
    for spec in specs:
        if _tree(spec.release_path) != _tree(spec.author_path):
            raise SuccessorInstallBlocked("RELEASE_SNAPSHOT_DRIFT", spec.bundle_id)
        if (spec.release_path / SIGNATURE_FILENAME).exists():
            raise SuccessorInstallBlocked("COMMITTED_SIGNATURE_FORBIDDEN", spec.bundle_id)
        loaded = unsigned.load(spec.source_ref)
        actual_ids = tuple(item.module_id for item in loaded.workshop_modules)
        actual_routes = tuple(item.route for item in loaded.workshop_modules)
        if set(actual_ids) != set(spec.expected_module_ids) or set(actual_routes) != set(spec.expected_routes):
            raise SuccessorInstallBlocked("MODULE_INVENTORY_DRIFT", spec.bundle_id)
        if seen_ids.intersection(actual_ids) or seen_routes.intersection(actual_routes):
            raise SuccessorInstallBlocked("MODULE_ID_ROUTE_COLLISION", spec.bundle_id)
        seen_ids.update(actual_ids)
        seen_routes.update(actual_routes)
        result.append({
            "bundleId": spec.bundle_id,
            "version": spec.version,
            "sourceRef": spec.source_ref,
            "contentHash": loaded.content_hash,
            "moduleIds": sorted(actual_ids),
            "routes": sorted(actual_routes),
        })
    if len(seen_ids) != 8 or len(seen_routes) != 8:
        raise SuccessorInstallBlocked("MODULE_INVENTORY_NOT_EIGHT", "expected 8 modules")
    return {"releaseSnapshots": result, "moduleCount": 8}


def _canonical_signature_payload(loaded: Any) -> bytes:
    payload = {
        "manifest": loaded.manifest.model_dump(mode="json", by_alias=True, exclude_none=False),
        "artifacts": [
            {
                "relativePath": item.relative_path,
                "digest": item.digest,
                "size": item.size,
                "mediaType": item.media_type,
            }
            for item in loaded.artifacts
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _trust_root(key: Ed25519PrivateKey, key_id: str) -> TrustRoot:
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return TrustRoot(
        publisher=PUBLISHER,
        key_id=key_id,
        public_key=public,
        revision=canonical_sha256({
            "publisher": PUBLISHER,
            "keyId": key_id,
            "algorithm": "Ed25519",
            "publicKey": base64.b64encode(public).decode(),
        }),
        not_before=TRUST_NOT_BEFORE,
        not_after=TRUST_NOT_AFTER,
    )


def _load_keys() -> tuple[Ed25519PrivateKey, FrozenTrustRootProvider]:
    if not RUNTIME_KEY_PATH.is_file():
        raise SuccessorInstallBlocked("SIGNING_KEY_UNAVAILABLE", "runtime signing key unavailable")
    key = serialization.load_pem_private_key(RUNTIME_KEY_PATH.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SuccessorInstallBlocked("SIGNING_KEY_INVALID", "runtime signing key type invalid")
    roots = {(PUBLISHER, RUNTIME_KEY_ID): _trust_root(key, RUNTIME_KEY_ID)}
    legacy_path = REPOSITORY_ROOT / "scripts/.d2_6_runtime_ed25519.pem"
    if legacy_path.is_file():
        legacy = serialization.load_pem_private_key(legacy_path.read_bytes(), password=None)
        if isinstance(legacy, Ed25519PrivateKey):
            legacy_root = _trust_root(legacy, "d2-6-runtime-signer")
            roots[(PUBLISHER, legacy_root.key_id)] = legacy_root
    return key, FrozenTrustRootProvider(roots)


def _prepare_signed_loader(
    specs: Sequence[ReleaseSpec], key: Ed25519PrivateKey, trust: FrozenTrustRootProvider
) -> tuple[ManifestLoader, Path]:
    signed_root = Path(tempfile.mkdtemp(prefix="aos-workshop-w1-10-signed-"))
    try:
        for spec in specs:
            relative = spec.release_path.relative_to(REPOSITORY_ROOT / "bundles")
            shutil.copytree(spec.release_path, signed_root / relative)
        unsigned = ManifestLoader({SOURCE_ALIAS: signed_root})
        signed_at = datetime.now(UTC).isoformat()
        for spec in specs:
            loaded = unsigned.load(spec.source_ref)
            envelope = {
                "algorithm": "Ed25519",
                "keyId": RUNTIME_KEY_ID,
                "signature": base64.b64encode(key.sign(_canonical_signature_payload(loaded))).decode(),
                "signedAt": signed_at,
            }
            signature_path = signed_root / spec.release_path.relative_to(REPOSITORY_ROOT / "bundles") / SIGNATURE_FILENAME
            signature_path.write_text(json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n")
        return ManifestLoader({SOURCE_ALIAS: signed_root}, trust_roots=trust), signed_root
    except Exception:
        shutil.rmtree(signed_root, ignore_errors=True)
        raise


def _expected_version(loaded: Any) -> dict[str, Any]:
    manifest = loaded.manifest.model_dump(mode="json", by_alias=True, exclude_none=False)
    return {
        "status": "published",
        "sourceRef": loaded.source_ref,
        "contentHash": loaded.content_hash,
        "manifestHash": canonical_sha256(manifest),
        "artifacts": sorted(
            (
                {
                    "relativePath": item.relative_path,
                    "artifactRef": item.artifact_ref,
                    "digest": item.digest,
                }
                for item in loaded.artifacts
            ),
            key=lambda item: item["artifactRef"],
        ),
    }


def _comparable_version(record: dict[str, Any]) -> dict[str, Any]:
    artifacts = sorted(
        ({"artifactRef": item["artifactRef"], "digest": item["digest"]} for item in record.get("artifacts", [])),
        key=lambda item: item["artifactRef"],
    )
    refs = {
        item["artifactRef"][: -(len(source["relativePath"]) + 1)]
        for item, source in zip(artifacts, sorted(record.get("artifacts", []), key=lambda entry: entry["artifactRef"]))
        if source.get("relativePath") and item["artifactRef"].endswith("/" + source["relativePath"])
    }
    source_ref = record.get("sourceRef") or (next(iter(refs)) if len(refs) == 1 else None)
    manifest_hash = record.get("manifestHash")
    if manifest_hash is None and isinstance(record.get("manifest"), dict):
        manifest_hash = canonical_sha256(record["manifest"])
    return {
        "status": str(record.get("status", "")).lower(),
        "sourceRef": source_ref,
        "contentHash": record.get("contentHash"),
        "manifestHash": manifest_hash,
        "artifacts": artifacts,
    }


def assert_existing_version_exact(existing: dict[str, Any], expected: dict[str, Any]) -> None:
    if _comparable_version(existing) != _comparable_version(expected):
        raise SuccessorInstallBlocked("EXISTING_VERSION_DRIFT", "existing published version is not exact")


def _database_clock() -> datetime:
    with connect() as conn:
        return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]


def publish_releases(
    specs: Sequence[ReleaseSpec], loader: ManifestLoader, trust: FrozenTrustRootProvider
) -> list[dict[str, Any]]:
    store = PostgresRegistryStore(connect_factory=connect)
    service = RegistryService(store=store, loader=loader, clock=_database_clock, trust_roots=trust)
    published: list[dict[str, Any]] = []
    for spec in specs:
        loaded = loader.load(spec.source_ref)
        expected = _expected_version(loaded)
        try:
            existing = store.get_version(spec.bundle_id, spec.version, publisher=PUBLISHER)
        except AssetNotFoundError:
            existing = None
        if existing is None:
            service.create_version(
                publisher=PUBLISHER, bundle_id=spec.bundle_id, source_ref=spec.source_ref,
                actor=f"{IDEMPOTENCY_PREFIX}-{spec.version}-creator", roles=REGISTRY_ROLES,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            service.validate(
                publisher=PUBLISHER, bundle_id=spec.bundle_id, version=spec.version,
                actor=f"{IDEMPOTENCY_PREFIX}-{spec.version}-validator", roles=PUBLISH_ROLES,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            service.publish(
                publisher=PUBLISHER, bundle_id=spec.bundle_id, version=spec.version,
                actor=f"{IDEMPOTENCY_PREFIX}-{spec.version}-publisher", roles=PUBLISH_ROLES,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            existing = store.get_version(spec.bundle_id, spec.version, publisher=PUBLISHER)
        assert_existing_version_exact(existing, expected)
        published.append(expected)
    return published


def _active_rows() -> list[Any]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT i.installation_id, i.active_revision,
                   r.overlay_revision, r.lock_hash AS revision_lock_hash,
                   c.composition_id, l.revision AS lock_revision, l.lock_payload,
                   l.lock_hash, l.permission_diff_json, l.permission_diff_hash,
                   l.migration_plan_json, l.migration_plan_hash,
                   l.contribution_diff_json, l.contribution_diff_hash, l.created_at
              FROM bundle_installation i
              JOIN bundle_installation_revision r
                ON r.org_id=i.org_id AND r.project_id=i.project_id
               AND r.installation_pk=i.installation_pk AND r.revision=i.active_revision
              JOIN bundle_composition c
                ON c.org_id=r.org_id AND c.project_id=r.project_id
               AND c.composition_pk=r.composition_pk
              JOIN bundle_composition_lock l
                ON l.org_id=r.org_id AND l.project_id=r.project_id
               AND l.composition_pk=r.composition_pk AND l.revision=r.lock_revision
             WHERE i.org_id=%s AND i.project_id=%s
               AND i.active_revision IS NOT NULL AND r.state='active'
             ORDER BY i.installation_id
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchall()


def current_effective_ref() -> CurrentInstallationRef:
    leaves = _effective_active_rows(_active_rows())
    if len(leaves) != 1:
        raise SuccessorInstallBlocked("EFFECTIVE_INSTALLATION_AMBIGUOUS", f"effective leaves={len(leaves)}")
    row, lock = leaves[0]
    return CurrentInstallationRef.model_validate({
        "installationId": str(row["installation_id"]),
        "revision": int(row["active_revision"]),
        "lockHash": lock.lock_hash,
        "overlayRevision": str(row["overlay_revision"]),
    })


def create_successor(trust: FrozenTrustRootProvider, current: CurrentInstallationRef) -> InstallationResponse:
    release_policy = ReleasePolicy(trust_roots=trust)
    installation_store = PostgresInstallationStore(connect_factory=connect)
    composition_store = PostgresCompositionStore(connect_factory=connect)
    snapshot_reader = RegistrySnapshotReader(connect_factory=connect, release_policy=release_policy)
    composition = CompositionService(
        snapshot_reader=snapshot_reader,
        composition_store=composition_store,
        command_store=installation_store,
        baseline_reader=installation_store,
    )
    snapshot = snapshot_reader.read()
    request = CompositionRequest.model_validate({
        "requested": [
            {"publisher": PUBLISHER, "id": "platform.ecommerce.niushop", "version": "1.0.0"},
            {"publisher": PUBLISHER, "id": "solution.ecommerce.operations-base", "version": "1.1.0"},
            {"publisher": PUBLISHER, "id": "solution.ecommerce.growth", "version": "1.3.0"},
        ],
        "platformApiVersion": "1.7.0",
        "platformRelease": "aos-platform/1.7.0",
        "environment": "dev",
        "registrySnapshotHash": snapshot.snapshot_hash,
        "currentInstallationRef": current.model_dump(mode="json", by_alias=True),
    })
    receipt = composition.resolve(
        request=request, org_id=ORG_ID, project_id=PROJECT_ID, actor=MAKER,
        roles=MAKER_ROLES, markings=MARKINGS,
        idempotency_key=f"{IDEMPOTENCY_PREFIX}-composition",
    )
    lock = StoredCompositionLock.model_validate_json(json.dumps(receipt.response_json, default=str))
    resolved = {(item.id, item.version) for item in lock.payload.resolved}
    expected = {
        ("domain.ecommerce.core", "1.0.0"),
        ("platform.ecommerce.niushop", "1.0.0"),
        ("solution.ecommerce.operations-base", "1.1.0"),
        ("solution.ecommerce.growth", "1.3.0"),
    }
    if resolved != expected:
        raise SuccessorInstallBlocked("COMPOSITION_RESOLUTION_DRIFT", str(sorted(resolved)))

    service = InstallationService(
        store=installation_store,
        composition_store=composition_store,
        revalidator=InstallationRevalidator(release_policy=release_policy),
    )
    created = service.create(
        request=CreateInstallationRequest.model_validate({
            "compositionId": lock.composition_id,
            "lockRevision": lock.revision,
            "overlayRevision": "workshop-w1-10-eight-modules-v1",
            "displayName": "栖月汇电商工作台 · 八 Module canonical successor",
        }),
        org_id=ORG_ID, project_id=PROJECT_ID, actor=MAKER, roles=MAKER_ROLES,
        markings=MARKINGS, idempotency_key=f"{IDEMPOTENCY_PREFIX}-create",
    )
    response = InstallationResponse.model_validate_json(json.dumps(created.response_json, default=str))
    installation_id = response.installation_id

    def advance(name: str, actor: str, roles: frozenset[str], request_body: Any) -> InstallationResponse:
        nonlocal response
        method = getattr(service, name)
        transition = method(
            installation_id=installation_id, request=request_body,
            org_id=ORG_ID, project_id=PROJECT_ID, actor=actor, roles=roles,
            markings=MARKINGS, idempotency_key=f"{IDEMPOTENCY_PREFIX}-{name}",
            if_match=f'"{response.etag_version}"',
        )
        response = InstallationResponse.model_validate_json(json.dumps(transition.response_json, default=str))
        return response

    advance("submit", MAKER, MAKER_ROLES, EmptyInstallationActionRequest())
    advance("approve", CHECKER, CHECKER_ROLES, ApproveInstallationRequest.model_validate({
        "lockHash": lock.lock_hash,
        "permissionDiffHash": lock.permission_diff_hash,
        "migrationPlanHash": lock.migration_plan_hash,
        "contributionDiffHash": lock.contribution_diff_hash,
    }))
    advance("apply", MAKER, MAKER_ROLES, EmptyInstallationActionRequest())
    advance("verify", MAKER, MAKER_ROLES, EmptyInstallationActionRequest())
    if response.state != "active" or response.current_revision != 5:
        raise SuccessorInstallBlocked("INSTALLATION_NOT_ACTIVE", response.state)
    leaves = _effective_active_rows(_active_rows())
    if len(leaves) != 1 or str(leaves[0][0]["installation_id"]) != installation_id:
        raise SuccessorInstallBlocked("SUCCESSOR_NOT_EFFECTIVE", installation_id)
    return response


def run(*, apply: bool) -> dict[str, Any]:
    specs = release_specs()
    evidence = validate_release_snapshots(specs)
    evidence.update({"orgId": ORG_ID, "projectId": PROJECT_ID, "mode": "apply" if apply else "dry-run"})
    if not apply:
        evidence["outcome"] = "PREFLIGHT_GREEN"
        return evidence
    key, trust = _load_keys()
    loader, signed_root = _prepare_signed_loader(specs, key, trust)
    try:
        evidence["published"] = publish_releases(specs, loader, trust)
        baseline = current_effective_ref()
        evidence["baselineInstallationRef"] = baseline.model_dump(mode="json", by_alias=True)
        successor = create_successor(trust, baseline)
        evidence["successor"] = {
            "installationId": successor.installation_id,
            "state": successor.state,
            "revision": successor.current_revision,
            "etagVersion": successor.etag_version,
        }
        evidence["outcome"] = "CANONICAL_SUCCESSOR_ACTIVE"
        return evidence
    finally:
        shutil.rmtree(signed_root, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        evidence = run(apply=args.apply)
    except SuccessorInstallBlocked as exc:
        evidence = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.reason_code, "message": str(exc)}
        status = 2
    else:
        status = 0
    rendered = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
