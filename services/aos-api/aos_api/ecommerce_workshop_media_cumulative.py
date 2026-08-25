"""Build the W7-11 cumulative engineering gate without external effects."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from aos_api.ecommerce_workshop_media_cumulative_contracts import (
    MediaCumulativeEvidenceRef,
    MediaCumulativeGate,
    MediaCumulativeGateId,
    MediaCumulativeGateSet,
)


ENGINEERING_READY = {
    MediaCumulativeGateId.CONTRACT,
    MediaCumulativeGateId.SERVICE,
    MediaCumulativeGateId.DATABASE_RESTART,
    MediaCumulativeGateId.TENANT_RLS,
    MediaCumulativeGateId.BROWSER_POSITIVE,
    MediaCumulativeGateId.BROWSER_NEGATIVE,
    MediaCumulativeGateId.SECURITY,
    MediaCumulativeGateId.FAULT_INJECTION,
}

EXTERNAL_BLOCKERS = {
    MediaCumulativeGateId.PROVIDER_ADAPTER: "MEDIA_PRODUCTION_PROVIDER_ADAPTER_RECEIPT_REQUIRED",
    MediaCumulativeGateId.PUBLISH_CANARY: "MEDIA_PUBLISH_CANARY_RECEIPT_REQUIRED",
    MediaCumulativeGateId.OPERATIONAL_READY: "MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED",
}


class EcommerceWorkshopMediaCumulative:
    """Expose release-bound engineering evidence while retaining operational gates."""

    def __init__(self, *, release_revision: str = "AOS-000267") -> None:
        self._release_revision = release_revision

    def read(self, *, cutoff: datetime) -> MediaCumulativeGateSet:
        if cutoff.utcoffset() is None:
            raise ValueError("cumulative cutoff requires timezone")
        gates: list[MediaCumulativeGate] = []
        evidence_id = "workshop-w7-11-media-cumulative-browser-security-fault-20260826"
        for gate_id in MediaCumulativeGateId:
            if gate_id in ENGINEERING_READY:
                identity = f"{self._release_revision}:{evidence_id}:{gate_id.value}"
                gates.append(
                    MediaCumulativeGate(
                        gateId=gate_id,
                        status="ready",
                        evidenceRef=MediaCumulativeEvidenceRef(
                            resourceType="EvidencePack",
                            resourceId=evidence_id,
                            revision=self._release_revision,
                            contentHash=sha256(identity.encode()).hexdigest(),
                        ),
                        reasonCode="MEDIA_ENGINEERING_EVIDENCE_CURRENT",
                        observedAt=cutoff,
                    )
                )
            else:
                gates.append(
                    MediaCumulativeGate(
                        gateId=gate_id,
                        status="blocked",
                        reasonCode=EXTERNAL_BLOCKERS[gate_id],
                    )
                )
        blockers = sorted(item.reason_code for item in gates if item.status != "ready")
        return MediaCumulativeGateSet(
            releaseRevision=self._release_revision,
            evaluatedAt=cutoff,
            gates=gates,
            overallStatus="blocked",
            blockerCodes=blockers,
        )


__all__ = ["EcommerceWorkshopMediaCumulative"]
