"""Installed Bundle authority for exact ResponsibilityTemplateRevision refs.

The Registry and the tenant's active installation remain the only lifecycle
authorities.  This module only verifies that an exact signed Bundle artifact is
present in the active composition lock; it never returns or stores its payload.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
import hashlib
import json
from pathlib import Path
from typing import Any

from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]

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
    }
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

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def resolve(self, scope: TenantScope, ref: ExactRevisionRef) -> bool:
        if ref.resource_type != "ResponsibilityTemplateRevision":
            return False
        if not ref.resource_id.startswith("bundle://"):
            return False
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
            return False
        return any(self._row_matches(row, ref) for row in rows)

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
    return _INSTALLED_RESOLVER.resolve(scope, ref)


def bundle_path_hint() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "bundles/releases/ecommerce/solution.ecommerce.growth/1.3.0"
    )
