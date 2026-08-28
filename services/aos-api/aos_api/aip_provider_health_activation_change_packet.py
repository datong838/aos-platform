"""Deterministic, non-executable Provider Health activation change packet."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from aos_api.aip_provider_health_activation_readiness import (
    ProviderHealthActivationReadiness,
)


PACKET_SCHEMA = "aos.provider-health-activation-change-packet/v1"
CANONICAL_TENANT = "org-org/dev-project"


@dataclass(frozen=True, slots=True)
class ProviderHealthChangeStep:
    step_id: str
    effect_class: str
    depends_on: tuple[str, ...] = ()
    required_gate: str | None = None
    clears_codes: tuple[str, ...] = ()

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "stepId": self.step_id,
            "effectClass": self.effect_class,
            "dependsOn": list(self.depends_on),
            "requiredGate": self.required_gate,
            "clearsCodes": list(self.clears_codes),
        }


@dataclass(frozen=True, slots=True)
class ProviderHealthActivationChangePacket:
    packet_id: str
    schema: str
    tenant: str
    expected_deployed_revision: str
    readiness_status: str
    execution_authorized: bool
    authorization_status: str
    current_missing: tuple[str, ...]
    change_steps: tuple[ProviderHealthChangeStep, ...]
    rollback_steps: tuple[ProviderHealthChangeStep, ...]

    def as_public_dict(self) -> dict[str, Any]:
        """Expose an audit description only; this object cannot execute steps."""
        return {
            "packetId": self.packet_id,
            "schema": self.schema,
            "tenant": self.tenant,
            "expectedDeployedRevision": self.expected_deployed_revision,
            "readinessStatus": self.readiness_status,
            "executionAuthorized": self.execution_authorized,
            "authorizationStatus": self.authorization_status,
            "currentMissing": list(self.current_missing),
            "changeSteps": [step.as_public_dict() for step in self.change_steps],
            "rollbackSteps": [
                step.as_public_dict() for step in self.rollback_steps
            ],
        }


def _change_steps() -> tuple[ProviderHealthChangeStep, ...]:
    return (
        ProviderHealthChangeStep("PHC-01-VERIFY-BASELINE", "read_only"),
        ProviderHealthChangeStep(
            "PHC-02-DEPLOY-EXACT-REVISION",
            "controlled_change",
            ("PHC-01-VERIFY-BASELINE",),
            clears_codes=("DEPLOYED_REVISION_NOT_EXACT",),
        ),
        ProviderHealthChangeStep(
            "PHC-03-INSTALL-PLUGIN-AND-ACTIONTYPE",
            "controlled_change",
            ("PHC-02-DEPLOY-EXACT-REVISION",),
            clears_codes=(
                "PROVIDER_HEALTH_ACTION_PLUGIN_NOT_INSTALLED",
                "PROVIDER_HEALTH_ACTION_TYPE_NOT_EXACT",
            ),
        ),
        ProviderHealthChangeStep(
            "PHC-04-CONFIGURE-CANONICAL-STARTUP",
            "controlled_change",
            ("PHC-03-INSTALL-PLUGIN-AND-ACTIONTYPE",),
            clears_codes=("CANONICAL_ENVIRONMENT_NOT_EXACT",),
        ),
        ProviderHealthChangeStep(
            "PHC-05-RESTART-SINGLE-INSTANCE",
            "controlled_change",
            ("PHC-04-CONFIGURE-CANONICAL-STARTUP",),
        ),
        ProviderHealthChangeStep(
            "PHC-06-VERIFY-LOOP-GATE",
            "read_only",
            ("PHC-05-RESTART-SINGLE-INSTANCE",),
            required_gate="loop_ready",
        ),
        ProviderHealthChangeStep(
            "PHC-07-ISSUE-EXACT-ACTION-AUTHORITY",
            "controlled_change",
            ("PHC-06-VERIFY-LOOP-GATE",),
            clears_codes=(
                "PROVIDER_HEALTH_PROPOSAL_NOT_EXACT",
                "PROVIDER_HEALTH_APPROVAL_NOT_EXACT",
                "PROVIDER_HEALTH_LEASE_NOT_EXACT",
                "PROVIDER_HEALTH_RECEIPT_AUTHORITY_NOT_EXACT",
                "PROVIDER_HEALTH_LEASE_NOT_FRESH",
            ),
        ),
        ProviderHealthChangeStep(
            "PHC-08-VERIFY-PROVIDER-CALL-GATE",
            "read_only",
            ("PHC-07-ISSUE-EXACT-ACTION-AUTHORITY",),
            required_gate="provider_call_ready",
        ),
        ProviderHealthChangeStep(
            "PHC-09-RUN-ONE-BOUNDED-HEALTH-ACTION",
            "bounded_external_effect",
            ("PHC-08-VERIFY-PROVIDER-CALL-GATE",),
        ),
        ProviderHealthChangeStep(
            "PHC-10-WAIT-NATURAL-SOURCE-READINESS",
            "read_only",
            ("PHC-09-RUN-ONE-BOUNDED-HEALTH-ACTION",),
        ),
        ProviderHealthChangeStep(
            "PHC-11-VERIFY-REAL-PILOT-GATE",
            "read_only",
            ("PHC-10-WAIT-NATURAL-SOURCE-READINESS",),
            required_gate="pilot_ready",
        ),
    )


def _rollback_steps() -> tuple[ProviderHealthChangeStep, ...]:
    return (
        ProviderHealthChangeStep(
            "PHR-01-FENCE-PROVIDER-CALLS", "controlled_change"
        ),
        ProviderHealthChangeStep(
            "PHR-02-DISABLE-CANONICAL-LOOP",
            "controlled_change",
            ("PHR-01-FENCE-PROVIDER-CALLS",),
        ),
        ProviderHealthChangeStep(
            "PHR-03-RESTART-SINGLE-INSTANCE-FAIL-CLOSED",
            "controlled_change",
            ("PHR-02-DISABLE-CANONICAL-LOOP",),
        ),
        ProviderHealthChangeStep(
            "PHR-04-VERIFY-LOOP-ABSENT",
            "read_only",
            ("PHR-03-RESTART-SINGLE-INSTANCE-FAIL-CLOSED",),
        ),
        ProviderHealthChangeStep(
            "PHR-05-RESTORE-PLUGIN-ACTIONTYPE-STATE",
            "controlled_change",
            ("PHR-04-VERIFY-LOOP-ABSENT",),
        ),
        ProviderHealthChangeStep(
            "PHR-06-RESTORE-REVISION-AND-ENV-SNAPSHOT",
            "controlled_change",
            ("PHR-05-RESTORE-PLUGIN-ACTIONTYPE-STATE",),
        ),
        ProviderHealthChangeStep(
            "PHR-07-VERIFY-BASELINE",
            "read_only",
            ("PHR-06-RESTORE-REVISION-AND-ENV-SNAPSHOT",),
        ),
    )


def build_provider_health_activation_change_packet(
    readiness: ProviderHealthActivationReadiness,
) -> ProviderHealthActivationChangePacket:
    """Build a plan-only packet that can never authorize or execute itself."""
    if readiness.provider_call_ready and not readiness.loop_ready:
        raise ValueError("provider-call readiness requires loop readiness")
    if readiness.pilot_ready and not readiness.provider_call_ready:
        raise ValueError("pilot readiness requires provider-call readiness")

    change_steps = _change_steps()
    rollback_steps = _rollback_steps()
    identity = {
        "schema": PACKET_SCHEMA,
        "tenant": CANONICAL_TENANT,
        "evaluatedAt": readiness.evaluated_at.isoformat(),
        "expectedDeployedRevision": readiness.expected_deployed_revision,
        "readinessStatus": readiness.status,
        "currentMissing": list(readiness.pilot_missing),
        "changeStepIds": [step.step_id for step in change_steps],
        "rollbackStepIds": [step.step_id for step in rollback_steps],
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ProviderHealthActivationChangePacket(
        packet_id=f"phc_{digest[:24]}",
        schema=PACKET_SCHEMA,
        tenant=CANONICAL_TENANT,
        expected_deployed_revision=readiness.expected_deployed_revision,
        readiness_status=readiness.status,
        execution_authorized=False,
        authorization_status="SEPARATE_EXACT_APPROVAL_REQUIRED",
        current_missing=readiness.pilot_missing,
        change_steps=change_steps,
        rollback_steps=rollback_steps,
    )


__all__ = [
    "CANONICAL_TENANT",
    "PACKET_SCHEMA",
    "ProviderHealthActivationChangePacket",
    "ProviderHealthChangeStep",
    "build_provider_health_activation_change_packet",
]
