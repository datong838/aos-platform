"""Fail-closed Workshop facade over canonical SourceReadiness.

This adapter owns no readiness facts.  It delegates one principal-scoped read
to the Data/Adapter owner and rejects any tenant drift in the returned
envelope.
"""

from __future__ import annotations

from typing import Protocol

from aos_api.source_readiness_contracts import SourceReadinessEnvelope


class CanonicalSourceReadinessReader(Protocol):
    def read(self, *, org_id: str, project_id: str) -> SourceReadinessEnvelope: ...


class SourceReadinessTenantMismatchError(RuntimeError):
    """The canonical reader returned facts for a different tenant."""


class EcommerceWorkshopSourceReadiness:
    """Expose canonical readiness without persisting or reclassifying it."""

    def __init__(self, reader: CanonicalSourceReadinessReader) -> None:
        self._reader = reader

    def read(self, *, org_id: str, project_id: str) -> SourceReadinessEnvelope:
        envelope = self._reader.read(org_id=org_id, project_id=project_id)
        if (
            envelope.tenant.org_id != org_id
            or envelope.tenant.project_id != project_id
        ):
            raise SourceReadinessTenantMismatchError(
                "canonical SourceReadiness tenant does not match principal scope"
            )
        return envelope
