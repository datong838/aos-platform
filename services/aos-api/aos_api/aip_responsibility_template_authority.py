"""Installed Bundle authority for exact production-template revision refs.

The Registry and the tenant's active installation remain the only lifecycle
authorities. This module verifies exact signed Bundle artifacts against the
active composition lock before loading typed payloads from the immutable mirror.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
import hashlib
import json
from pathlib import Path
from typing import Any

from aos_api.aip_media_production_templates import (
    MediaResponsibilityTemplate,
    MediaStageTemplate,
)
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_production_profile_contracts import ProductionProfile
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]
_PROFILE_RESOURCE_TYPES = {
    "ProductionProfileRevision",
    "ResponsibilityTemplateRevision",
    "StageTemplateRevision",
    "EvidenceSelectionProfileRevision",
    "EvalProfileRevision",
}

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
        self._release_root = release_root or (
            Path(__file__).resolve().parents[3] / "bundles/releases/ecommerce"
        )

    def resolve(self, scope: TenantScope, ref: ExactRevisionRef) -> bool:
        if ref.resource_type not in _PROFILE_RESOURCE_TYPES:
            return False
        if not ref.resource_id.startswith("bundle://"):
            return False
        return any(self._row_matches(row, ref) for row in self._fetch_rows(scope, ref))

    def _fetch_rows(self, scope: TenantScope, ref: ExactRevisionRef) -> list[Any]:
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """
                    SELECT installation.installation_id,
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
        release_root = (
            self._release_root / str(row["bundle_id"]) / str(row["version"])
        ).resolve()
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


_INSTALLED_RESOLVER = InstalledProductionProfileResolver()


def resolve_responsibility_template(scope: TenantScope, ref: ExactRevisionRef) -> bool:
    """Production adapter retained for AipProductionContractStore injection."""
    definition = _TEMPLATE_DEFINITIONS.get(ref.resource_id)
    if definition is not None and ref.resource_id == "ecommerce.business-investigation.readonly":
        return ref == published_template_ref(ref.resource_id)
    return _INSTALLED_RESOLVER.resolve(scope, ref)


def bundle_path_hint() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "bundles/releases/ecommerce/solution.ecommerce.growth/1.3.0"
    )
