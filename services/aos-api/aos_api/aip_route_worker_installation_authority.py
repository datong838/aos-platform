"""Bind the Route worker identity document to one current signed installation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from aos_api.aip_route_worker_identity import RouteWorkerIdentityConfig
from aos_api.aip_route_worker_installation import (
    RouteWorkerIdentityInstallation,
    RouteWorkerIdentityInstallationStore,
    RouteWorkerInstallationBlocked,
    RouteWorkerSignedRelease,
    release_set_hash,
)
from aos_api.extension_runtime.current_installation_release_evidence import (
    CurrentInstallationReleaseEvidence,
    read_current_installation_release_evidence,
)
from aos_api.tenant_scope import TenantScope


class CurrentRouteWorkerInstallationAuthority:
    """Exact read-only authority; it never starts runtime or changes installation."""

    def __init__(self, *, reader: Callable[..., CurrentInstallationReleaseEvidence]):
        if not callable(reader):
            raise TypeError("reader required")
        self._reader = reader

    @classmethod
    def from_runtime(cls) -> CurrentRouteWorkerInstallationAuthority:
        from aos_api.asset_registry.control_wiring import (
            _REPOSITORY_ROOT,
            _allowlist_roots,
            _configured_trust_roots,
        )
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.extension_runtime.runtime_connections import (
            runtime_directory_connection,
        )

        roots = _configured_trust_roots()
        policy = ReleasePolicy(trust_roots=roots)
        loader = ManifestLoader(
            _allowlist_roots(repository_root=_REPOSITORY_ROOT), trust_roots=roots
        )

        def reader(**kwargs):
            return read_current_installation_release_evidence(
                connect_factory=runtime_directory_connection,
                release_policy=policy,
                loader=loader,
                **kwargs,
            )

        return cls(reader=reader)

    @staticmethod
    def _releases(evidence: CurrentInstallationReleaseEvidence):
        return tuple(
            sorted(
                (
                    RouteWorkerSignedRelease(
                        publisher=item.publisher,
                        bundleId=item.bundle_id,
                        version=item.version,
                        contentHash=item.content_hash,
                        signatureFingerprint=item.signature_fingerprint,
                        releaseEvidenceRevision=item.release_evidence_revision,
                    )
                    for item in evidence.releases
                ),
                key=lambda item: item.sort_key(),
            )
        )

    def _read_current(
        self, *, scope: TenantScope, installation_id: str
    ) -> CurrentInstallationReleaseEvidence:
        evidence = self._reader(scope=scope, installation_id=installation_id)
        if (
            type(evidence) is not CurrentInstallationReleaseEvidence
            or evidence.authorization != "EVIDENCE_ONLY_NO_START"
            or evidence.scope != scope.key
            or evidence.installation_id != installation_id
            or evidence.active_revision != evidence.current_revision
            or not evidence.releases
        ):
            raise ValueError
        return evidence

    def build_document(
        self, *, config: RouteWorkerIdentityConfig, installation_id: str
    ) -> RouteWorkerIdentityInstallation:
        try:
            if type(config) is not RouteWorkerIdentityConfig:
                raise ValueError
            scope = TenantScope("org-org", "dev-project")
            evidence = self._read_current(scope=scope, installation_id=installation_id)
            releases = self._releases(evidence)
            return RouteWorkerIdentityInstallation(
                orgId=scope.org_id,
                projectId=scope.project_id,
                issuer=config.issuer,
                audience=config.audience,
                tokenEndpoint=config.token_endpoint,
                clientId=config.client_id,
                expectedSubject=config.expected_subject,
                secretVersion=config.secret_version,
                installationId=evidence.installation_id,
                installationRevision=evidence.current_revision,
                installationEtag=evidence.etag_version,
                lockHash=evidence.lock_hash,
                releases=releases,
                releaseSetHash=release_set_hash(releases),
            )
        except RouteWorkerInstallationBlocked:
            raise
        except Exception:
            raise RouteWorkerInstallationBlocked(
                "ROUTE_WORKER_SIGNED_INSTALLATION_REQUIRED"
            ) from None

    def assert_current(self, document: RouteWorkerIdentityInstallation) -> bool:
        try:
            if type(document) is not RouteWorkerIdentityInstallation:
                raise ValueError
            scope = TenantScope(document.orgId, document.projectId)
            evidence = self._read_current(
                scope=scope, installation_id=document.installationId
            )
            if (
                evidence.current_revision != document.installationRevision
                or evidence.etag_version != document.installationEtag
                or evidence.lock_hash != document.lockHash
            ):
                raise ValueError
            releases = self._releases(evidence)
            if (
                releases != document.releases
                or release_set_hash(releases) != document.releaseSetHash
            ):
                raise ValueError
            return True
        except RouteWorkerInstallationBlocked:
            raise
        except Exception:
            raise RouteWorkerInstallationBlocked(
                "ROUTE_WORKER_SIGNED_INSTALLATION_REQUIRED"
            ) from None


class RouteWorkerSignedInstallationCoordinator:
    """Fail closed around file publication when signed authority drifts."""

    def __init__(
        self,
        *,
        store: RouteWorkerIdentityInstallationStore,
        authority: CurrentRouteWorkerInstallationAuthority,
    ) -> None:
        self._store = store
        self._authority = authority

    def install(
        self,
        path: str | Path,
        document: RouteWorkerIdentityInstallation,
        *,
        expected_current_hash: str | None = None,
    ) -> str:
        self._authority.assert_current(document)
        return self._store.install(
            path,
            document,
            expected_current_hash=expected_current_hash,
            post_publish_check=self._authority.assert_current,
        )

    def uninstall(self, path: str | Path, *, expected_current_hash: str):
        current = self._store.load(path)
        self._authority.assert_current(current)
        return self._store.uninstall(path, expected_current_hash=expected_current_hash)
