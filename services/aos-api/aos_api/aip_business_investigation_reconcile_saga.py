"""BI-W6-05 fail-closed coordination for ambiguous cross-layer commands."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Literal, Protocol

from pydantic import model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl,
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationRunStateWrite,
    BusinessInvestigationRunView,
    BusinessInvestigationUncertainCommand,
)
from aos_api.tenant_scope import TenantScope


SCHEMA_VERSION = "aos.aip.business-investigation-reconciliation-coordination/v1"
ALLOWED_OPERATIONS = frozenset(
    {
        "business_investigation.compile",
        "data_requirement.request",
        "data_requirement.fulfill",
        "business_investigation.artifact.publish",
    }
)


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _state_ref(state: BusinessInvestigationRunStateRevision) -> InvestigationExactRef:
    return InvestigationExactRef(
        resource_type="BusinessInvestigationRunStateRevision",
        resource_id=state.run_id,
        revision=state.version,
        content_hash=state.content_hash,
    )


class BusinessInvestigationReconciliationCoordination(AipContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    tenant: TenantContext
    phase: Literal["UNKNOWN", "RECONCILING"]
    uncertain_command: BusinessInvestigationUncertainCommand
    prior_state_ref: InvestigationExactRef
    current_state_ref: InvestigationExactRef
    replayed: bool
    original_command_replayed: Literal[False] = False
    outcome_resolved: Literal[False] = False
    external_effect_authorized: Literal[False] = False

    @model_validator(mode="after")
    def _exact_state_lineage(self) -> BusinessInvestigationReconciliationCoordination:
        for ref in (self.prior_state_ref, self.current_state_ref):
            if ref.resource_type != "BusinessInvestigationRunStateRevision":
                raise ValueError("coordination refs must bind Run state revisions")
        if (
            self.prior_state_ref.resource_id != self.current_state_ref.resource_id
            or not isinstance(self.prior_state_ref.revision, int)
            or not isinstance(self.current_state_ref.revision, int)
            or self.current_state_ref.revision != self.prior_state_ref.revision + 1
        ):
            raise ValueError("coordination Run state lineage drifted")
        return self


class BusinessInvestigationReconciliationConflict(RuntimeError):
    pass


class CanonicalRunStateAuthority(Protocol):
    def get(self, scope: TenantScope, run_id: str) -> BusinessInvestigationRunView: ...

    def mark_unknown(
        self,
        scope: TenantScope,
        run_id: str,
        uncertain_command: BusinessInvestigationUncertainCommand,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateWrite: ...

    def begin_reconcile(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateWrite: ...


class BusinessInvestigationReconciliationCoordinator:
    """Move ambiguous commands to UNKNOWN/RECONCILING without replaying them."""

    def __init__(self, runs: CanonicalRunStateAuthority) -> None:
        self._runs = runs

    def record_timeout(
        self,
        scope: TenantScope,
        run_id: str,
        observed_state_ref: InvestigationExactRef,
        uncertain_command: BusinessInvestigationUncertainCommand,
        *,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationReconciliationCoordination:
        self._validate_common(scope, run_id, observed_state_ref, uncertain_command, actor, occurred_at)
        current = self._runs.get(scope, run_id).state
        replay_state = (
            current.control is BusinessInvestigationRunControl.UNKNOWN
            and current.uncertain_command == uncertain_command
            and current.prior_ref == observed_state_ref
        )
        if not replay_state:
            self._require_current(current, observed_state_ref)
            if current.control not in {
                BusinessInvestigationRunControl.RUNNING,
                BusinessInvestigationRunControl.PAUSED,
            }:
                raise BusinessInvestigationReconciliationConflict(
                    "timeout may only mark a stable Run UNKNOWN"
                )
        result = self._runs.mark_unknown(
            scope,
            run_id,
            uncertain_command,
            expected_version=int(observed_state_ref.revision),
            idempotency_key=self._idempotency_key(
                scope, "unknown", observed_state_ref, uncertain_command
            ),
            actor=actor.strip(),
            occurred_at=occurred_at,
        )
        return self._result(scope, "UNKNOWN", observed_state_ref, uncertain_command, result)

    def begin_reconcile(
        self,
        scope: TenantScope,
        run_id: str,
        observed_unknown_ref: InvestigationExactRef,
        uncertain_command: BusinessInvestigationUncertainCommand,
        *,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationReconciliationCoordination:
        self._validate_common(
            scope, run_id, observed_unknown_ref, uncertain_command, actor, occurred_at
        )
        current = self._runs.get(scope, run_id).state
        replay_state = (
            current.control is BusinessInvestigationRunControl.RECONCILING
            and current.uncertain_command == uncertain_command
            and current.prior_ref == observed_unknown_ref
        )
        if not replay_state:
            self._require_current(current, observed_unknown_ref)
            if current.control is not BusinessInvestigationRunControl.UNKNOWN:
                raise BusinessInvestigationReconciliationConflict(
                    "reconcile requires current UNKNOWN Run state"
                )
            if current.uncertain_command != uncertain_command:
                raise BusinessInvestigationReconciliationConflict(
                    "reconcile uncertain command drifted"
                )
        result = self._runs.begin_reconcile(
            scope,
            run_id,
            expected_version=int(observed_unknown_ref.revision),
            idempotency_key=self._idempotency_key(
                scope, "reconciling", observed_unknown_ref, uncertain_command
            ),
            actor=actor.strip(),
            occurred_at=occurred_at,
        )
        return self._result(
            scope, "RECONCILING", observed_unknown_ref, uncertain_command, result
        )

    @staticmethod
    def _validate_common(
        scope: TenantScope,
        run_id: str,
        observed_ref: InvestigationExactRef,
        command: BusinessInvestigationUncertainCommand,
        actor: str,
        occurred_at: datetime,
    ) -> None:
        if not run_id.strip() or len(run_id) > 200 or not actor.strip():
            raise BusinessInvestigationReconciliationConflict("run id and actor are required")
        if occurred_at.utcoffset() is None:
            raise BusinessInvestigationReconciliationConflict("occurredAt must include timezone")
        if (
            observed_ref.resource_type != "BusinessInvestigationRunStateRevision"
            or observed_ref.resource_id != run_id
            or not isinstance(observed_ref.revision, int)
        ):
            raise BusinessInvestigationReconciliationConflict("exact Run state ref is required")
        if command.operation not in ALLOWED_OPERATIONS:
            raise BusinessInvestigationReconciliationConflict(
                "uncertain command operation is outside the controlled allowlist"
            )

    @staticmethod
    def _require_current(
        current: BusinessInvestigationRunStateRevision,
        observed_ref: InvestigationExactRef,
    ) -> None:
        if _state_ref(current) != observed_ref:
            raise BusinessInvestigationReconciliationConflict("observed Run state drifted")

    @staticmethod
    def _idempotency_key(
        scope: TenantScope,
        phase: str,
        observed_ref: InvestigationExactRef,
        command: BusinessInvestigationUncertainCommand,
    ) -> str:
        digest = _canonical_hash(
            {
                "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                "phase": phase,
                "observedStateRef": observed_ref.model_dump(mode="json", by_alias=True),
                "uncertainCommand": command.model_dump(mode="json", by_alias=True),
            }
        )
        return f"bi-reconcile-{phase}-{digest}"

    @staticmethod
    def _result(
        scope: TenantScope,
        phase: Literal["UNKNOWN", "RECONCILING"],
        prior_ref: InvestigationExactRef,
        command: BusinessInvestigationUncertainCommand,
        write: BusinessInvestigationRunStateWrite,
    ) -> BusinessInvestigationReconciliationCoordination:
        state = write.authority
        if (
            (state.tenant.org_id, state.tenant.project_id) != scope.key
            or state.run_id != prior_ref.resource_id
            or state.prior_ref != prior_ref
            or state.control.value != phase
            or state.uncertain_command != command
        ):
            raise BusinessInvestigationReconciliationConflict(
                "canonical Run state transition result drifted"
            )
        return BusinessInvestigationReconciliationCoordination(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            phase=phase,
            uncertain_command=command,
            prior_state_ref=prior_ref,
            current_state_ref=_state_ref(state),
            replayed=write.replayed,
        )


__all__ = [
    "ALLOWED_OPERATIONS",
    "BusinessInvestigationReconciliationConflict",
    "BusinessInvestigationReconciliationCoordination",
    "BusinessInvestigationReconciliationCoordinator",
]
