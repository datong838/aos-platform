"""Canonical orchestration for fail-closed external ResearchJobs."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_research_job import (
    CreateResearchJobRequest,
    ReconcileResearchJobRequest,
    RecordResearchArtifactRequest,
    RecordResearchDeliveryRequest,
    RecordResearchSubmissionRequest,
    RegisterResearchProviderRequest,
    ResearchArtifactReceipt,
    ResearchDeliveryReceipt,
    ResearchJobEvent,
    ResearchJobSnapshot,
    ResearchProviderRevision,
    ResearchProviderStatus,
    ResearchSubmissionReceipt,
    verify_research_callback,
)
from aos_api.aip_research_job_store import (
    AipResearchJobBlocked,
    AipResearchJobStore,
)
from aos_api.tenant_scope import TenantScope

CallbackSecretResolver = Callable[[TenantScope, str, int], bytes]
ArtifactHashResolver = Callable[[TenantScope, str], str]


def _missing_secret(
    _scope: TenantScope, _provider_id: str, _provider_revision: int
) -> bytes:
    raise AipResearchJobBlocked("research callback secret resolver is unavailable")


def _missing_artifact_hash(_scope: TenantScope, _content_ref: str) -> str:
    raise AipResearchJobBlocked("research artifact hash resolver is unavailable")


class AipResearchJobService:
    """Validate transport/content facts before appending them to PostgreSQL."""

    def __init__(
        self,
        store: AipResearchJobStore | None = None,
        *,
        secret_resolver: CallbackSecretResolver = _missing_secret,
        artifact_hash_resolver: ArtifactHashResolver = _missing_artifact_hash,
    ) -> None:
        self._store = store or AipResearchJobStore()
        self._secret_resolver = secret_resolver
        self._artifact_hash_resolver = artifact_hash_resolver

    def register_provider(
        self,
        scope: TenantScope,
        request: RegisterResearchProviderRequest,
        actor: str,
        *,
        now: datetime | None = None,
    ) -> ResearchProviderRevision:
        return self._store.register_provider(
            scope, request, actor, now or datetime.now(UTC)
        )

    def create_job(
        self,
        scope: TenantScope,
        request: CreateResearchJobRequest,
        actor: str,
        *,
        now: datetime | None = None,
    ) -> ResearchJobSnapshot:
        return self._store.create_job(scope, request, actor, now or datetime.now(UTC))

    def record_submission(
        self,
        scope: TenantScope,
        request: RecordResearchSubmissionRequest,
        *,
        now: datetime | None = None,
    ) -> ResearchSubmissionReceipt:
        return self._store.record_submission(scope, request, now or datetime.now(UTC))

    def record_event(
        self,
        scope: TenantScope,
        job_id: str,
        event: ResearchJobEvent,
        *,
        now: datetime | None = None,
    ) -> ResearchJobSnapshot:
        actual_hash = hashlib.sha256(self._canonical_payload(event.payload)).hexdigest()
        if not hmac.compare_digest(actual_hash, event.payload_hash):
            raise AipResearchJobBlocked("provider event payload hash mismatch")
        return self._store.record_event(scope, job_id, event, now or datetime.now(UTC))

    def verify_callback(
        self,
        scope: TenantScope,
        *,
        provider_id: str,
        provider_revision: int,
        timestamp: int,
        nonce: str,
        body: bytes,
        signature: str,
        observed_at: datetime | None = None,
    ) -> str:
        now = observed_at or datetime.now(UTC)
        provider = self._store.get_current_provider(
            scope, provider_id, provider_revision
        )
        if provider.status is not ResearchProviderStatus.ENABLED:
            raise AipResearchJobBlocked("research provider is disabled")
        secret = self._secret_resolver(scope, provider_id, provider_revision)
        try:
            body_hash = verify_research_callback(
                secret=secret,
                timestamp=timestamp,
                nonce=nonce,
                body=body,
                signature=signature,
                seen_nonces=set(),
                now=now,
            )
        except ValueError as exc:
            raise AipResearchJobBlocked(str(exc)) from exc
        nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
        self._store.record_callback_nonce(
            scope,
            provider.provider_id,
            provider.revision,
            nonce_hash,
            body_hash,
            timestamp,
            now,
            datetime.now(UTC),
        )
        return body_hash

    def record_artifact(
        self,
        scope: TenantScope,
        request: RecordResearchArtifactRequest,
        actor: str,
        *,
        now: datetime | None = None,
    ) -> ResearchArtifactReceipt:
        actual_hash = self._artifact_hash_resolver(scope, request.content_ref)
        if not hmac.compare_digest(actual_hash.lower(), request.content_hash):
            raise AipResearchJobBlocked("research artifact content hash mismatch")
        return self._store.record_artifact(
            scope, request, actor, now or datetime.now(UTC)
        )

    def record_delivery(
        self,
        scope: TenantScope,
        request: RecordResearchDeliveryRequest,
        *,
        now: datetime | None = None,
    ) -> ResearchDeliveryReceipt:
        return self._store.record_delivery(scope, request, now or datetime.now(UTC))

    def reconcile(
        self,
        scope: TenantScope,
        request: ReconcileResearchJobRequest,
        *,
        now: datetime | None = None,
    ) -> ResearchDeliveryReceipt:
        return self._store.reconcile(scope, request, now or datetime.now(UTC))

    def get_job(self, scope: TenantScope, job_id: str) -> ResearchJobSnapshot:
        return self._store.get_job(scope, job_id)

    @staticmethod
    def _canonical_payload(payload: object) -> bytes:
        import json

        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()


__all__ = ["AipResearchJobService"]
