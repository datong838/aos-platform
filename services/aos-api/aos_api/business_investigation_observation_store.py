"""PostgreSQL authority access for BI-W3 read-only observation leases/plans."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import psycopg
from psycopg.types.json import Jsonb

from aos_api.business_investigation_observation_contracts import (
    ObservationPlanRevisionRecord,
    ObservationReceiptRecord,
    ObservationSessionLeaseRecord,
)
from aos_api.db import connect as db_connect
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]
AuthorityT = TypeVar("AuthorityT")


class BusinessInvestigationObservationError(RuntimeError):
    code = "BUSINESS_INVESTIGATION_OBSERVATION_ERROR"


class BusinessInvestigationObservationConflict(BusinessInvestigationObservationError):
    code = "BUSINESS_INVESTIGATION_OBSERVATION_CONFLICT"


class BusinessInvestigationObservationValidationError(BusinessInvestigationObservationError):
    code = "BUSINESS_INVESTIGATION_OBSERVATION_VALIDATION_ERROR"


@dataclass(frozen=True, slots=True)
class ObservationAuthorityWrite(Generic[AuthorityT]):
    authority: AuthorityT
    replayed: bool


class BusinessInvestigationObservationStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def read_receipt_exact(self, scope: TenantScope, ref: InvestigationExactRef) -> ObservationReceiptRecord | None:
        """Read historical owner authority; never rerun observation or infer fulfillment."""
        if (ref.resource_type != "ObservationReceipt" or type(ref.revision) is not int
                or ref.revision != 1 or ref.receipt_id not in (None, ref.resource_id)):
            raise BusinessInvestigationObservationValidationError("exact observation receipt reference required")
        with self._connect_factory(scope) as conn:
            row = conn.execute("""SELECT * FROM business_investigation_observation_receipt
                WHERE org_id=%s AND project_id=%s AND receipt_id=%s""", (*scope.key, ref.resource_id)).fetchone()
        if row is None:
            return None
        try:
            item = ObservationReceiptRecord.model_validate(row["authority_data"])
        except (TypeError, ValueError) as exc:
            raise BusinessInvestigationObservationValidationError("invalid observation authority payload") from exc
        self._scope_matches(scope, item.tenant.org_id, item.tenant.project_id)
        expected = {
            "org_id": scope.org_id, "project_id": scope.project_id, "receipt_id": item.receipt_id,
            "plan_id": item.plan_ref.resource_id, "plan_revision": item.plan_ref.revision,
            "plan_content_hash": item.plan_ref.content_hash,
            "step_id": item.step_ref.resource_id.removeprefix(item.plan_ref.resource_id + ":"),
            "capability_id": item.capability_ref.resource_id, "lease_id": item.session_ref.resource_id,
            "lease_revision": item.session_ref.revision, "lease_content_hash": item.session_ref.content_hash,
            "requirement_id": item.requirement_ref.resource_id, "requirement_revision": item.requirement_ref.revision,
            "requirement_content_hash": item.requirement_ref.content_hash, "status": item.status.value,
            "semantic_route": item.semantic_route, "cutoff_at": item.cutoff_at, "content_hash": item.content_hash,
            "idempotency_key": item.idempotency_key, "request_hash": item.request_hash,
        }
        if (item.receipt_id != ref.resource_id or item.content_hash != ref.content_hash
                or any(row[key] != value for key, value in expected.items())):
            raise BusinessInvestigationObservationValidationError("observation authority identity or lineage drifted")
        return item

    def issue_lease(
        self,
        scope: TenantScope,
        lease: ObservationSessionLeaseRecord,
    ) -> ObservationAuthorityWrite[ObservationSessionLeaseRecord]:
        self._scope_matches(scope, lease.tenant.org_id, lease.tenant.project_id)
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM observation_lease_issue_biw3_001(%s,%s,%s,%s)",
            (
                lease.lease_id,
                lease.idempotency_key,
                lease.request_hash,
                Jsonb(lease.model_dump(by_alias=True, mode="json")),
            ),
        )
        return ObservationAuthorityWrite(
            authority=ObservationSessionLeaseRecord.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def revoke_lease(
        self,
        scope: TenantScope,
        lease_id: str,
        *,
        expected_state_version: int,
        idempotency_key: str,
        reason: str,
    ) -> ObservationSessionLeaseRecord:
        self._bounded("lease id", lease_id)
        self._bounded("idempotency key", idempotency_key)
        self._bounded("reason", reason)
        if expected_state_version < 1:
            raise BusinessInvestigationObservationValidationError(
                "expected state version must be positive"
            )
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM observation_lease_revoke_biw3_001(%s,%s,%s,%s)",
            (lease_id, expected_state_version, idempotency_key, reason),
        )
        return ObservationSessionLeaseRecord.model_validate(row["authority_data"])

    def publish_plan(
        self,
        scope: TenantScope,
        plan: ObservationPlanRevisionRecord,
        *,
        expected_version: int,
    ) -> ObservationAuthorityWrite[ObservationPlanRevisionRecord]:
        self._scope_matches(scope, plan.tenant.org_id, plan.tenant.project_id)
        if expected_version < 0:
            raise BusinessInvestigationObservationValidationError(
                "expected version must be non-negative"
            )
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM observation_plan_publish_biw3_001(%s,%s,%s,%s,%s)",
            (
                plan.plan_id,
                expected_version,
                plan.idempotency_key,
                plan.request_hash,
                Jsonb(plan.model_dump(by_alias=True, mode="json")),
            ),
        )
        return ObservationAuthorityWrite(
            authority=ObservationPlanRevisionRecord.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def record_receipt(
        self,
        scope: TenantScope,
        receipt: ObservationReceiptRecord,
    ) -> ObservationAuthorityWrite[ObservationReceiptRecord]:
        self._scope_matches(scope, receipt.tenant.org_id, receipt.tenant.project_id)
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM observation_receipt_record_biw3_002(%s,%s,%s,%s)",
            (
                receipt.receipt_id,
                receipt.idempotency_key,
                receipt.request_hash,
                Jsonb(receipt.model_dump(by_alias=True, mode="json")),
            ),
        )
        return ObservationAuthorityWrite(
            authority=ObservationReceiptRecord.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def _execute(self, scope: TenantScope, sql: str, params: tuple[Any, ...]):
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(sql, params).fetchone()
                if row is None:
                    raise BusinessInvestigationObservationConflict(
                        "observation command did not return authority"
                    )
                conn.commit()
                return row
        except psycopg.Error as exc:
            self._translate(exc)
            raise

    @staticmethod
    def _scope_matches(scope: TenantScope, org_id: str, project_id: str) -> None:
        if scope.key != (org_id, project_id):
            raise BusinessInvestigationObservationValidationError(
                "payload tenant must equal principal scope"
            )

    @staticmethod
    def _bounded(name: str, value: str) -> None:
        if not value.strip() or len(value) > 200:
            raise BusinessInvestigationObservationValidationError(
                f"{name} must be non-empty and bounded"
            )

    @staticmethod
    def _translate(exc: psycopg.Error) -> None:
        if exc.sqlstate == "BO001":
            raise BusinessInvestigationObservationValidationError(str(exc)) from exc
        if exc.sqlstate in {"BO002", "BO003", "23505", "23503"}:
            raise BusinessInvestigationObservationConflict(str(exc)) from exc
