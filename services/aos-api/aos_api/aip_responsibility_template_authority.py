"""Installed Bundle authority for exact production-template revision refs.

The Registry and the tenant's active installation remain the only lifecycle
authorities. This module verifies exact signed Bundle artifacts against the
active composition lock before loading typed payloads from the immutable mirror.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import Any

from aos_api.aip_media_production_templates import (
    MediaResponsibilityTemplate,
    MediaStageTemplate,
)
from aos_api.aip_business_investigation_responsibility_template import (
    BIResponsibilityTemplate, BI_TEMPLATE_SCHEMA,
)
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_production_profile_contracts import ProductionProfile
from aos_api.db import connect as db_connect, connect_read_only as db_connect_read_only
from aos_api.tenant_scope import TenantScope
from aos_api.asset_registry.legacy_runtime_boundary import legacy_content_predicate

ConnectFactory = Callable[..., AbstractContextManager[Any]]
_PROFILE_RESOURCE_TYPES = {
    "ProductionProfileRevision",
    "ResponsibilityTemplateRevision",
    "StageTemplateRevision",
    "EvidenceSelectionProfileRevision",
    "EvalProfileRevision",
}
_SIGNED_ROOT_PIN_LOCK = Lock()
_PINNED_SIGNED_RELEASE_ROOT: tuple[Path, int, int] | None = None
_BI_TEMPLATE_PATH = "content/responsibility-templates/business-investigation.readonly.json"
_BI_TEMPLATE_ID = "ecommerce.business-investigation.readonly"


def pin_verified_signed_release_root(root: Path) -> None:
    """Pin only a root returned by the current signed Host preflight."""
    global _PINNED_SIGNED_RELEASE_ROOT
    if root.is_symlink():
        raise ValueError("signed root cannot be a symlink")
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("signed root must be a directory")
    stat = resolved.stat()
    candidate = (resolved, stat.st_dev, stat.st_ino)
    with _SIGNED_ROOT_PIN_LOCK:
        if _PINNED_SIGNED_RELEASE_ROOT is not None and _PINNED_SIGNED_RELEASE_ROOT != candidate:
            raise ValueError("signed root changed in process")
        _PINNED_SIGNED_RELEASE_ROOT = candidate


def _current_pinned_signed_release_root() -> Path | None:
    pinned = _PINNED_SIGNED_RELEASE_ROOT
    if pinned is None:
        return None
    root, device, inode = pinned
    try:
        stat = root.stat()
        if root.resolve(strict=True) == root and root.is_dir() and (stat.st_dev, stat.st_ino) == (device, inode):
            return root
    except OSError:
        pass
    return None

# Stable L0 template definitions published with solution.ecommerce.growth.
# contentHash = sha256 of canonical JSON (sorted keys, no whitespace).
_TEMPLATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "ecommerce-standard": {
        "resourceType": "ResponsibilityTemplateRevision",
        "resourceId": "ecommerce-standard",
        "revision": 1,
        "profile": "ecommerce-standard",
        "sourceBundle": {
            "resourceType": "SolutionPack",
            "resourceId": "solution.ecommerce.growth",
            "revision": "1.3.0",
        },
        "slots": [
            {
                "slotId": "content.review",
                "responsibilityType": "independent_review",
                "requiredCapabilityIds": ["content.review"],
            }
        ],
    },
    "ecommerce.business-investigation.readonly": {
        "resourceType": "ResponsibilityTemplateRevision",
        "resourceId": "ecommerce.business-investigation.readonly",
        "revision": 1,
        "profile": "ecommerce.business-investigation.readonly",
        "sourceProfile": {
            "resourceType": "InvestigationProfileRevision",
            "resourceId": "ecommerce.initial-store-analysis",
            "revision": 1,
        },
        "slots": [
            "investigation-owner",
            "data-steward",
            "content-research",
            "customer-research",
            "channel-research",
            "business-reviewer",
        ],
        "safetyMode": "read-only",
    },
}


def _canonical_json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def published_template_ref(template_id: str) -> ExactRevisionRef:
    """Return the historical W-E1 ref for compatibility tooling only.

    Production resolution no longer trusts this local definition.
    """
    definition = _TEMPLATE_DEFINITIONS[template_id]
    return ExactRevisionRef(
        resource_type="ResponsibilityTemplateRevision",
        resource_id=template_id,
        revision=int(definition["revision"]),
        content_hash=_canonical_json_hash(definition),
    )


class InstalledProductionProfileResolver:
    """Resolve an exact artifact only through the tenant active installation."""

    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        *,
        release_root: Path | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._explicit_release_root = release_root is not None
        self._release_root = release_root or (
            Path(__file__).resolve().parents[3] / "bundles/releases/ecommerce"
        )

    def resolve(self, scope: TenantScope, ref: ExactRevisionRef) -> bool:
        if ref.resource_type not in _PROFILE_RESOURCE_TYPES:
            return False
        if not ref.resource_id.startswith("bundle://"):
            return False
        if ref.resource_type == "ResponsibilityTemplateRevision":
            try:
                raw = self._load_verified_bytes(scope, ref)
                if raw is None:
                    return False
                payload = json.loads(raw)
                if type(payload) is not dict:
                    return False
                schema = payload.get("schema")
                if schema == "aos.ecommerce-media-responsibility-template/v1":
                    MediaResponsibilityTemplate.model_validate(payload)
                    return True
                if schema == BI_TEMPLATE_SCHEMA:
                    BIResponsibilityTemplate.model_validate(payload)
                    return True
            except Exception:
                return False
            return False
        return any(self._row_matches(row, ref) for row in self._fetch_rows(scope, ref))

    def _fetch_rows(self, scope: TenantScope, ref: ExactRevisionRef) -> list[Any]:
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    f"""
                    SELECT {legacy_content_predicate('composition_lock')} AS legacy_eligible,
                           installation.installation_id,
                           installation.active_revision,
                           active.state AS installation_state,
                           composition_lock.lock_payload,
                           bundle.publisher,
                           bundle.bundle_id,
                           version.version,
                           version.content_hash AS bundle_content_hash,
                           version.signature,
                           version.status,
                           artifact.artifact_ref,
                           artifact.relative_path,
                           artifact.digest AS artifact_digest
                      FROM bundle_installation AS installation
                      JOIN bundle_installation_revision AS active
                        ON active.org_id=installation.org_id
                       AND active.project_id=installation.project_id
                       AND active.installation_pk=installation.installation_pk
                       AND active.revision=installation.active_revision
                      JOIN bundle_composition_lock AS composition_lock
                        ON composition_lock.org_id=active.org_id
                       AND composition_lock.project_id=active.project_id
                       AND composition_lock.composition_pk=active.composition_pk
                       AND composition_lock.revision=active.lock_revision
                      JOIN asset_bundle_artifact AS artifact
                        ON artifact.artifact_ref=%s
                      JOIN asset_bundle_version AS version
                        ON version.version_pk=artifact.version_pk
                      JOIN asset_bundle AS bundle
                        ON bundle.bundle_pk=version.bundle_pk
                     WHERE installation.org_id=%s
                       AND installation.project_id=%s
                       AND installation.active_revision=%s
                       AND artifact.artifact_ref=%s
                    """,
                    (
                        ref.resource_id,
                        scope.org_id,
                        scope.project_id,
                        ref.revision,
                        ref.resource_id,
                    ),
                ).fetchall()
        except Exception:
            return []
        return list(rows)

    def load_profile(
        self, scope: TenantScope, ref: ExactRevisionRef
    ) -> ProductionProfile | None:
        """Load a verified profile payload from the immutable release mirror."""
        if ref.resource_type != "ProductionProfileRevision":
            return None
        try:
            raw = self._load_verified_bytes(scope, ref)
            if raw is None:
                return None
            return ProductionProfile.model_validate_json(raw)
        except Exception:
            return None

    def load_media_responsibility_template(
        self, scope: TenantScope, ref: ExactRevisionRef
    ) -> MediaResponsibilityTemplate | None:
        """Load an exact media responsibility template from a signed installation."""
        if ref.resource_type != "ResponsibilityTemplateRevision":
            return None
        try:
            raw = self._load_verified_bytes(scope, ref)
            return (
                MediaResponsibilityTemplate.model_validate_json(raw)
                if raw is not None
                else None
            )
        except Exception:
            return None

    def load_media_stage_template(
        self, scope: TenantScope, ref: ExactRevisionRef
    ) -> MediaStageTemplate | None:
        """Load an exact media stage template from a signed installation."""
        if ref.resource_type != "StageTemplateRevision":
            return None
        try:
            raw = self._load_verified_bytes(scope, ref)
            return MediaStageTemplate.model_validate_json(raw) if raw is not None else None
        except Exception:
            return None

    def _load_verified_bytes(
        self, scope: TenantScope, ref: ExactRevisionRef
    ) -> bytes | None:
        row = next(
            (row for row in self._fetch_rows(scope, ref) if self._row_matches(row, ref)),
            None,
        )
        if row is None:
            return None
        relative = Path(str(row["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            return None
        base_root = self._release_root
        if not self._explicit_release_root:
            pinned_root = _current_pinned_signed_release_root()
            configured_root = os.getenv("AOS_BUNDLE_ROOT")
            if (os.getenv("AOS_CURRENT_SIGNED_RECEIPT") or configured_root) and pinned_root is None:
                return None
            if configured_root and pinned_root is not None:
                if Path(configured_root).resolve(strict=True) != pinned_root:
                    return None
            if pinned_root is not None:
                base_root = pinned_root
        release_root = (
            base_root / str(row["bundle_id"]) / str(row["version"])
        ).resolve()
        if base_root.resolve() not in release_root.parents:
            return None
        artifact_path = (release_root / relative).resolve()
        if release_root not in artifact_path.parents or not artifact_path.is_file():
            return None
        raw = artifact_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref.content_hash:
            return None
        return raw

    @staticmethod
    def _row_matches(row: Any, ref: ExactRevisionRef) -> bool:
        try:
            if row['legacy_eligible'] is not True:
                return False
            if int(row["active_revision"]) != ref.revision:
                return False
            if row["installation_state"] != "active":
                return False
            if row["status"] != "published" or not row["signature"]:
                return False
            if row["artifact_ref"] != ref.resource_id:
                return False
            if row["artifact_digest"] != f"sha256:{ref.content_hash}":
                return False

            publisher = str(row["publisher"])
            bundle_id = str(row["bundle_id"])
            version = str(row["version"])
            expected_prefix = f"bundle://{publisher}/{bundle_id}@{version}/"
            if not ref.resource_id.startswith(expected_prefix):
                return False

            lock_payload = row["lock_payload"]
            resolved = lock_payload.get("resolved", [])
            if not isinstance(resolved, list):
                return False
            for selected in resolved:
                if not isinstance(selected, dict):
                    continue
                if (
                    selected.get("publisher") == publisher
                    and selected.get("id") == bundle_id
                    and selected.get("version") == version
                    and selected.get("contentHash") == row["bundle_content_hash"]
                    and _is_sha256(selected.get("signatureFingerprint"))
                    and _is_sha256(selected.get("releaseEvidenceRevision"))
                ):
                    return True
        except (KeyError, TypeError, ValueError):
            return False
        return False


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


@dataclass(frozen=True)
class ApprovedBIPreparationSelection:
    installation_id: str
    template_ref: ExactRevisionRef
    template: BIResponsibilityTemplate


class ApprovedBIPreparationResolver:
    """Read a signed, uniquely approved BI template for configuration only.

    This never grants runtime admission and does not change the active resolver.
    """

    def __init__(
        self,
        connect_factory: ConnectFactory = db_connect_read_only,
        *,
        registry_connect_factory: Callable[[], AbstractContextManager[Any]] = db_connect,
        release_root: Path | None = None,
        trust_roots: Any = None,
        source_alias: str | None = None,
        registry_prepared_transaction: bool = False,
        restricted_bi_scope: TenantScope | None = None,
    ) -> None:
        if type(registry_prepared_transaction) is not bool:
            raise ValueError("registry transaction mode must be explicit")
        if (restricted_bi_scope is not None
                and (type(restricted_bi_scope) is not TenantScope
                     or not registry_prepared_transaction)):
            raise ValueError("restricted BI source requires one prepared tenant")
        self._connect_factory = connect_factory
        self._registry_connect_factory = registry_connect_factory
        self._release_root = release_root
        self._trust_roots = trust_roots
        self._source_alias = source_alias
        self._registry_prepared_transaction = registry_prepared_transaction
        self._restricted_bi_scope = restricted_bi_scope

    def select(self, scope: TenantScope) -> ApprovedBIPreparationSelection | None:
        if type(scope) is not TenantScope:
            return None
        if self._restricted_bi_scope is not None and scope != self._restricted_bi_scope:
            return None
        try:
            from aos_api.asset_registry.contracts import BundleVersionStatus
            from aos_api.asset_registry.manifest_loader import ManifestLoader
            from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
            from aos_api.asset_registry.release_policy import ReleasePolicy
            from aos_api.asset_registry.signature import FileTrustRootProvider

            root = self._release_root or Path(os.environ["AOS_BUNDLE_ROOT"])
            if root.is_symlink():
                return None
            root = root.resolve(strict=True)
            roots = self._trust_roots or FileTrustRootProvider.from_environment()
            roots = roots.snapshot()
            rows = self._approved_rows(scope)
            if not rows:
                return None
            snapshot = RegistrySnapshotReader(
                release_policy=ReleasePolicy(trust_roots=roots),
                connect_factory=self._registry_connect_factory,
                prepared_transaction=self._registry_prepared_transaction,
                restricted_bi_scope=self._restricted_bi_scope,
            ).read()
            matched = [(row, item) for row in rows for item in snapshot.candidates
                       if (item.publisher, item.id, item.version, item.content_hash)
                       == (row["publisher"], row["bundle_id"], row["version"],
                           row["bundle_content_hash"])
                       and self._lock_matches(row["lock_payload"], item)]
            if len(matched) != 1:
                return None
            row, candidate = matched[0]
            ref_text = str(row["artifact_ref"])
            if not ref_text.startswith("bundle://"):
                return None
            alias = ref_text.removeprefix("bundle://").split("/", 1)[0]
            configured_alias = self._source_alias or os.getenv("AOS_BUNDLE_SOURCE_ALIAS")
            if not configured_alias or alias != configured_alias:
                return None
            source = f"bundle://{alias}/{row['bundle_id']}/{row['version']}"
            if ref_text != f"{source}/{_BI_TEMPLATE_PATH}":
                return None
            loaded = ManifestLoader({alias: root}, trust_roots=roots).load(source)
            if loaded.content_hash != candidate.content_hash:
                return None
            record = SimpleNamespace(
                publisher=row["publisher"], manifest=loaded.manifest,
                content_hash=loaded.content_hash, signature=loaded.signature,
                status=BundleVersionStatus.PUBLISHED, evidence=loaded.evidence,
                artifacts=[{"relativePath": item.relative_path, "digest": item.digest,
                            "size": item.size, "mediaType": item.media_type}
                           for item in loaded.artifacts],
                persisted_manifest=loaded.manifest.model_dump(mode="json", by_alias=True),
            )
            ReleasePolicy(trust_roots=roots).evaluate(
                record, checked_at=datetime.now(UTC),
                expected_signature_fingerprint=candidate.signature_fingerprint,
            )
            artifacts = [item for item in loaded.artifacts
                         if item.artifact_ref == ref_text and
                         item.relative_path == _BI_TEMPLATE_PATH and
                         item.digest == row["artifact_digest"]]
            if len(artifacts) != 1:
                return None
            path = root / str(row["bundle_id"]) / str(row["version"]) / _BI_TEMPLATE_PATH
            if path.is_symlink() or not path.is_file():
                return None
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if f"sha256:{digest}" != artifacts[0].digest:
                return None
            template = BIResponsibilityTemplate.model_validate_json(raw)
            if template.template_id != _BI_TEMPLATE_ID:
                return None
            return ApprovedBIPreparationSelection(
                installation_id=str(row["installation_id"]),
                template_ref=ExactRevisionRef(
                    resource_type="ResponsibilityTemplateRevision",
                    resource_id=ref_text,
                    revision=int(row["current_revision"]), content_hash=digest,
                ), template=template,
            )
        except Exception:
            return None

    def resolve(self, scope: TenantScope, ref: ExactRevisionRef) -> bool:
        """AIP Plan creation only; business readers must use the active resolver."""
        selection = self.select(scope)
        return selection is not None and selection.template_ref == ref

    def _approved_rows(self, scope: TenantScope) -> list[Any]:
        return self._installation_rows(scope, active=False)

    def _installation_rows(self, scope: TenantScope, *, active: bool) -> list[Any]:
        if self._restricted_bi_scope is not None:
            if scope != self._restricted_bi_scope:
                return []
            kind = "active" if active else "approved"
            with self._connect_factory(scope) as conn:
                return [row["payload"] for row in conn.execute(
                    """SELECT payload FROM public.aos_bi_growth_registry_a0v_137(
                        %s,%s,%s)""", (*scope.key, kind))]
        state_predicate = (
            "installation.active_revision=installation.current_revision AND current.state='active'"
            if active else
            "installation.active_revision IS NULL AND current.state='approved'"
        )
        with self._connect_factory(scope) as conn:
            return list(conn.execute(
                """SELECT installation.installation_id, installation.current_revision,
                           composition_lock.lock_payload, bundle.publisher, bundle.bundle_id,
                           version.version, version.content_hash AS bundle_content_hash,
                           artifact.artifact_ref, artifact.digest AS artifact_digest
                      FROM bundle_installation AS installation
                      JOIN bundle_installation_revision AS current
                        ON current.org_id=installation.org_id
                       AND current.project_id=installation.project_id
                       AND current.installation_pk=installation.installation_pk
                       AND current.revision=installation.current_revision
                      JOIN bundle_composition_lock AS composition_lock
                        ON composition_lock.org_id=current.org_id
                       AND composition_lock.project_id=current.project_id
                       AND composition_lock.composition_pk=current.composition_pk
                       AND composition_lock.revision=current.lock_revision
                      JOIN asset_bundle_artifact AS artifact
                        ON artifact.relative_path=%s
                      JOIN asset_bundle_version AS version
                        ON version.version_pk=artifact.version_pk
                      JOIN asset_bundle AS bundle ON bundle.bundle_pk=version.bundle_pk
                     WHERE installation.org_id=%s AND installation.project_id=%s
                       AND """ + state_predicate + """
                       AND bundle.publisher='aos'
                       AND bundle.bundle_id='solution.ecommerce.growth'
                       AND version.version IN ('1.12.0','1.13.0')
                       AND version.status='published'""",
                (_BI_TEMPLATE_PATH, scope.org_id, scope.project_id),
            ).fetchall())

    @staticmethod
    def _lock_matches(lock_payload: Any, candidate: Any) -> bool:
        if not isinstance(lock_payload, dict):
            return False
        resolved = lock_payload.get("resolved")
        if not isinstance(resolved, list):
            return False
        matches = [item for item in resolved if isinstance(item, dict) and
                   (item.get("publisher"), item.get("id"), item.get("version"),
                    item.get("contentHash"), item.get("signatureFingerprint"),
                    item.get("releaseEvidenceRevision")) ==
                   (candidate.publisher, candidate.id, candidate.version,
                    candidate.content_hash, candidate.signature_fingerprint,
                    candidate.release_evidence_revision)]
        return len(matches) == 1


class ActiveBIBusinessResolver(ApprovedBIPreparationResolver):
    """BI-specific signed active source; approved preparation never grants work."""

    def _approved_rows(self, scope: TenantScope) -> list[Any]:
        return self._installation_rows(scope, active=True)

    def load(
        self, scope: TenantScope, ref: ExactRevisionRef, *, installation_id: str,
    ) -> BIResponsibilityTemplate | None:
        selection = self.select(scope)
        if (selection is None or selection.template_ref != ref
                or selection.installation_id != str(installation_id)):
            return None
        return selection.template


_ACTIVE_BI_RESOLVER = ActiveBIBusinessResolver()


def load_active_bi_template(
    scope: TenantScope, ref: ExactRevisionRef, installation_id: str,
) -> BIResponsibilityTemplate | None:
    return _ACTIVE_BI_RESOLVER.load(scope, ref, installation_id=installation_id)


_INSTALLED_RESOLVER = InstalledProductionProfileResolver()


def resolve_responsibility_template(scope: TenantScope, ref: ExactRevisionRef) -> bool:
    """Production adapter retained for AipProductionContractStore injection."""
    return _INSTALLED_RESOLVER.resolve(scope, ref)


def bundle_path_hint() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "bundles/releases/ecommerce/solution.ecommerce.growth/1.3.0"
    )
