"""Server-derived UI sessions for signed, content-addressed frontend bundles."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.asset_registry.composition_contracts import InstallationResponse
from aos_api.asset_registry.composition_store import load_stored_lock
from aos_api.asset_registry.errors import AssetRegistryError, ManifestInvalidError
from aos_api.asset_registry.installation_revalidation import _record_from_row
from aos_api.asset_registry.registry_snapshot import _SNAPSHOT_QUERY
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.extension_runtime.runtime_view import RuntimeUiSessionView


class FrontendUiManifest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schemaVersion: Literal["aos.dev/frontend-runtime/v1alpha1"]
    title: str = Field(min_length=1, max_length=160)
    entrypoint: str = Field(min_length=1, max_length=1024)
    initialRoute: str = Field(min_length=1, max_length=512)
    routeClaims: list[str] = Field(max_length=128)
    readOperationClaims: list[str] = Field(max_length=256)
    commandOperationClaims: list[str] = Field(max_length=256)

    @field_validator("entrypoint")
    @classmethod
    def _entrypoint_is_bundle_local_html(cls, value: str) -> str:
        if not value.startswith("frontend/") or not value.endswith(".html") or _unsafe_path(value):
            raise ValueError("frontend entrypoint must be bundle-local HTML")
        return value

    @field_validator("initialRoute")
    @classmethod
    def _initial_route_is_canonical(cls, value: str) -> str:
        if not _canonical_route(value):
            raise ValueError("initialRoute must be canonical")
        return value

    @field_validator("routeClaims")
    @classmethod
    def _routes_are_exact_and_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("route claims must be unique")
        for value in values:
            base = value[:-2] if value.endswith("/*") else value
            if not _canonical_route(base):
                raise ValueError("route claim must be canonical")
        return values

    @field_validator("readOperationClaims", "commandOperationClaims")
    @classmethod
    def _operations_are_exact_and_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not _exact_operation(value) for value in values):
            raise ValueError("operation claims must be exact and unique")
        return values

    @model_validator(mode="after")
    def _claims_are_unambiguous(self) -> "FrontendUiManifest":
        if not _route_is_claimed(self.initialRoute, self.routeClaims):
            raise ValueError("initialRoute must be covered by routeClaims")
        if set(self.readOperationClaims) & set(self.commandOperationClaims):
            raise ValueError("read and command claims must be disjoint")
        return self


class ProductionUiSessionResolver:
    """Resolve UI metadata only from the current lock and revalidated release."""

    def __init__(self, *, connect_factory: Any, release_policy: Any, loader: Any, resource_origin: str | None) -> None:
        self._connect_factory = connect_factory
        self._release_policy = release_policy
        self._loader = loader
        self._resource_origin = _resource_origin(resource_origin)

    def __call__(
        self,
        *,
        installation: InstallationResponse,
        org_id: str,
        project_id: str,
        installation_id: str,
        installation_revision: int,
        generation: str,
        execution_epoch: int,
        roles: list[str],
        markings: list[str],
    ) -> RuntimeUiSessionView | None:
        del generation, execution_epoch, roles, markings
        if self._resource_origin is None:
            return None
        if not isinstance(installation, InstallationResponse):
            return None
        if installation.installation_id != installation_id or installation.current_revision != installation_revision:
            return None
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                _, lock = load_stored_lock(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    composition_id=installation.current.composition_id,
                    revision=installation.current.lock_revision,
                )
                clock = conn.execute("SELECT clock_timestamp() AS checked_at").fetchone()
                if clock is None:
                    return None
                rows = conn.execute(_SNAPSHOT_QUERY).fetchall()
            policy = self._release_policy.snapshot()
            indexed = {}
            for row in rows:
                key = (str(row["publisher"]), str(row["bundle_id"]), str(row["version"]))
                if key in indexed:
                    return None
                indexed[key] = row
            candidates: list[tuple[Any, Any]] = []
            for selected in lock.payload.resolved:
                row = indexed.get((selected.publisher, selected.id, selected.version))
                if row is None:
                    return None
                record = _record_from_row(row)
                if record.content_hash != selected.content_hash:
                    return None
                policy.evaluate(
                    record,
                    checked_at=clock["checked_at"],
                    expected_signature_fingerprint=selected.signature_fingerprint,
                    expected_evidence_revision=selected.release_evidence_revision,
                )
                if record.manifest.spec.runtime and record.manifest.spec.runtime.frontend:
                    candidates.append((selected, record))
            if len(candidates) != 1:
                return None
            selected, record = candidates[0]
            frontend = record.manifest.spec.runtime.frontend
            source_ref = _source_ref(record)
            if source_ref is None:
                return None
            loaded = self._loader.load(source_ref)
            if loaded.content_hash != selected.content_hash or loaded.manifest != record.manifest:
                return None
            artifacts = {item.relative_path: item for item in loaded.artifacts}
            manifest_artifact = artifacts.get(frontend.manifest)
            if manifest_artifact is None or manifest_artifact.digest != frontend.artifact_hash:
                return None
            raw = self._loader.read_verified_artifact(
                source_ref,
                frontend.manifest,
                expected_digest=manifest_artifact.digest,
                limit=65_536,
            )
            ui = FrontendUiManifest.model_validate_json(raw)
            entry = artifacts.get(ui.entrypoint)
            if entry is None:
                return None
            resource_url = _resource_url(
                self._resource_origin,
                publisher=selected.publisher,
                bundle_id=selected.id,
                version=selected.version,
                entrypoint=ui.entrypoint,
                package_hash=selected.content_hash,
                resource_hash=entry.digest,
            )
            return RuntimeUiSessionView(
                title=ui.title,
                signedResourceUrl=resource_url,
                resourceHash=entry.digest,
                initialRoute=ui.initialRoute,
                routeClaims=tuple(ui.routeClaims),
                readOperationClaims=tuple(ui.readOperationClaims),
                commandOperationClaims=tuple(ui.commandOperationClaims),
            )
        except (AssetRegistryError, ManifestInvalidError, TypeError, ValueError, KeyError):
            return None


def _unsafe_path(value: str) -> bool:
    return value.startswith(("/", "~")) or "\\" in value or "://" in value or any(part in {"", ".", ".."} for part in value.split("/"))


def _canonical_route(value: str) -> bool:
    if not value.startswith("/") or any(marker in value for marker in ("\\", "%", "?", "#", "//")):
        return False
    return value == "/" or all(part not in {"", ".", ".."} for part in value[1:].split("/"))


def _route_is_claimed(route: str, claims: list[str]) -> bool:
    return any(claim == route or (claim.endswith("/*") and route.startswith(claim[:-1])) for claim in claims)


def _exact_operation(value: str) -> bool:
    return bool(value) and value == value.strip() and len(value) <= 240 and all(character.isalnum() or character in "._:-" for character in value)


def _resource_origin(value: str | None) -> str | None:
    if value is None or value != value.strip():
        return None
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}):
        return None
    if not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _source_ref(record: Any) -> str | None:
    refs = {
        evidence.artifact_ref.removesuffix("/bundle.yaml")
        for evidence in record.evidence
        if str(getattr(evidence.type, "value", evidence.type)) == "content_hash" and evidence.artifact_ref.endswith("/bundle.yaml")
    }
    return next(iter(refs)) if len(refs) == 1 else None


def _resource_url(origin: str, *, publisher: str, bundle_id: str, version: str, entrypoint: str, package_hash: str, resource_hash: str) -> str:
    path = "/".join(quote(value, safe="") for value in (publisher, bundle_id, version, *entrypoint.split("/")))
    query = urlencode({"packageHash": package_hash, "contentHash": resource_hash})
    return f"{origin}/v1/bundles/{path}?{query}"
