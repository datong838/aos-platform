"""Postgres authority store for W6-08 customer contact governance."""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

from aos_api.db import connect
from aos_api.ecommerce_workshop_customer_contact import (
    CustomerBatchStartDecisionRevision,
    CustomerConsentWithdrawalObservation,
    CustomerContactBlocked,
    CustomerDispatchObservation,
    CustomerFrequencyPolicyRevision,
    CustomerFrequencyReservationRevision,
    StartCustomerDialogueBatchRequest,
)
from aos_api.ecommerce_workshop_customer_contracts import CustomerExactRef
from aos_api.ecommerce_workshop_customer_lifecycle import CustomerConsentPolicyRevision
from aos_api.tenant_scope import TenantScope


class EcommerceWorkshopCustomerContactStore:
    def __init__(self, connect_factory: Callable[[TenantScope], Any] = connect) -> None:
        self._connect = connect_factory

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _assert_tenant(scope: TenantScope, item: Any) -> None:
        if (item.tenant.org_id, item.tenant.project_id) != scope.key:
            raise CustomerContactBlocked("CUSTOMER_CONTACT_TENANT_DRIFTED")

    def _append(
        self,
        scope: TenantScope,
        table: str,
        identity_column: str,
        identity: str,
        revision: int,
        content_hash: str,
        item: Any,
        created_at: datetime,
        *,
        extra_columns: str = "",
        extra_values: tuple[Any, ...] = (),
    ) -> Any:
        self._assert_tenant(scope, item)
        columns = f",{extra_columns}" if extra_columns else ""
        placeholders = "," + ",".join("%s" for _ in extra_values) if extra_values else ""
        with self._connect(scope) as conn:
            conn.execute(
                f"INSERT INTO {table}(org_id,project_id,{identity_column},revision{columns},content_hash,authority_data,created_at) VALUES (%s,%s,%s,%s{placeholders},%s,%s::jsonb,%s) ON CONFLICT DO NOTHING",
                (*scope.key, identity, revision, *extra_values, content_hash, self._json(item.model_dump(mode="json", by_alias=True)), created_at),
            )
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s",
                (*scope.key, identity, revision),
            ).fetchone()
            if row is None or row["content_hash"] != content_hash:
                raise CustomerContactBlocked("CUSTOMER_CONTACT_IDEMPOTENCY_CONFLICT")
            conn.commit()
        return type(item).model_validate(row["authority_data"])

    def append_frequency_policy(self, scope: TenantScope, item: CustomerFrequencyPolicyRevision) -> CustomerFrequencyPolicyRevision:
        return self._append(scope, "ecommerce_customer_frequency_policy_revision", "policy_id", item.policy_id, item.revision, item.content_hash, item, item.created_at)

    def append_withdrawal(self, scope: TenantScope, item: CustomerConsentWithdrawalObservation) -> CustomerConsentWithdrawalObservation:
        return self._append(
            scope, "ecommerce_customer_consent_withdrawal_observation", "observation_id", item.observation_id,
            item.revision, item.content_hash, item, item.observed_at,
            extra_columns="customer_id,consent_policy_id,sequence",
            extra_values=(item.customer_ref.resource_id, item.consent_policy_ref.resource_id, item.sequence),
        )

    @staticmethod
    def _inside_quiet_hours(item: CustomerFrequencyPolicyRevision, at: datetime) -> bool:
        try:
            local = at.astimezone(ZoneInfo(item.timezone)).strftime("%H:%M")
        except ZoneInfoNotFoundError as exc:
            raise CustomerContactBlocked("CUSTOMER_FREQUENCY_TIMEZONE_INVALID") from exc
        start, end = item.quiet_hours_start, item.quiet_hours_end
        return start <= local < end if start < end else local >= start or local < end

    def reserve_frequency(self, scope: TenantScope, item: CustomerFrequencyReservationRevision) -> CustomerFrequencyReservationRevision:
        self._assert_tenant(scope, item)
        with self._connect(scope) as conn:
            # Tenant scope is applied before the store receives the connection,
            # so transaction characteristics can no longer be changed here.
            # Serialize the mutable frequency bucket explicitly instead.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"{scope.org_id}:{scope.project_id}:{item.customer_ref.resource_id}:{item.frequency_policy_ref.resource_id}",),
            )
            existing = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_customer_frequency_reservation_revision WHERE org_id=%s AND project_id=%s AND reservation_id=%s AND revision=1",
                (*scope.key, item.reservation_id),
            ).fetchone()
            if existing is not None:
                if existing["content_hash"] != item.content_hash:
                    raise CustomerContactBlocked("CUSTOMER_FREQUENCY_RESERVATION_IDEMPOTENCY_CONFLICT")
                return CustomerFrequencyReservationRevision.model_validate(existing["authority_data"])
            policy_row = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_customer_frequency_policy_revision WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s",
                (*scope.key, item.frequency_policy_ref.resource_id, item.frequency_policy_ref.revision),
            ).fetchone()
            if policy_row is None or f"sha256:{policy_row['content_hash']}" != item.frequency_policy_ref.content_hash:
                raise CustomerContactBlocked("CUSTOMER_FREQUENCY_POLICY_MISSING_OR_DRIFTED")
            policy = CustomerFrequencyPolicyRevision.model_validate(policy_row["authority_data"])
            if self._inside_quiet_hours(policy, item.created_at):
                raise CustomerContactBlocked("CUSTOMER_FREQUENCY_QUIET_HOURS_BLOCKED")
            cutoff = item.created_at - timedelta(hours=policy.rolling_window_hours)
            held = conn.execute(
                "SELECT COUNT(*) AS count FROM ecommerce_customer_frequency_reservation_revision WHERE org_id=%s AND project_id=%s AND customer_id=%s AND policy_id=%s AND status='held' AND created_at>=%s",
                (*scope.key, item.customer_ref.resource_id, policy.policy_id, cutoff),
            ).fetchone()["count"]
            if held >= policy.maximum_contacts:
                raise CustomerContactBlocked("CUSTOMER_FREQUENCY_LIMIT_EXCEEDED")
            conn.execute(
                "INSERT INTO ecommerce_customer_frequency_reservation_revision(org_id,project_id,reservation_id,revision,customer_id,policy_id,sequence,status,content_hash,authority_data,created_at) VALUES (%s,%s,%s,1,%s,%s,%s,'held',%s,%s::jsonb,%s)",
                (*scope.key, item.reservation_id, item.customer_ref.resource_id, policy.policy_id, item.sequence, item.content_hash, self._json(item.model_dump(mode="json", by_alias=True)), item.created_at),
            )
            conn.commit()
        return item

    def append_start(self, scope: TenantScope, batch_id: str, item: CustomerBatchStartDecisionRevision) -> CustomerBatchStartDecisionRevision:
        return self._append(
            scope, "ecommerce_customer_batch_start_decision_revision", "decision_id", item.decision_id,
            item.revision, item.content_hash, item, item.started_at, extra_columns="batch_id", extra_values=(batch_id,),
        )

    def append_dispatch_observation(self, scope: TenantScope, item: CustomerDispatchObservation) -> CustomerDispatchObservation:
        return self._append(
            scope, "ecommerce_customer_dispatch_observation", "observation_id", item.observation_id,
            item.revision, item.content_hash, item, item.observed_at,
            extra_columns="decision_id,item_key", extra_values=(item.start_decision_ref.resource_id, item.item_key),
        )

    def require_consent_policy(self, scope: TenantScope, ref: CustomerExactRef) -> CustomerConsentPolicyRevision:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_customer_consent_policy_revision WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or f"sha256:{row['content_hash']}" != ref.content_hash:
            raise CustomerContactBlocked("CUSTOMER_CONSENT_POLICY_MISSING_OR_DRIFTED")
        return CustomerConsentPolicyRevision.model_validate(row["authority_data"])

    def latest_withdrawal_or_none(self, scope: TenantScope, customer_ref: CustomerExactRef, consent_policy_ref: CustomerExactRef) -> CustomerConsentWithdrawalObservation | None:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT authority_data FROM ecommerce_customer_consent_withdrawal_observation WHERE org_id=%s AND project_id=%s AND customer_id=%s AND consent_policy_id=%s ORDER BY sequence DESC,created_at DESC LIMIT 1",
                (*scope.key, customer_ref.resource_id, consent_policy_ref.resource_id),
            ).fetchone()
        return None if row is None else CustomerConsentWithdrawalObservation.model_validate(row["authority_data"])

    def require_start_authorities(self, scope: TenantScope, request: StartCustomerDialogueBatchRequest) -> None:
        del scope, request
        # No caller-shaped exact refs are accepted as production authority.
        # A future resolver must bind all W5 records at one cutoff.
        raise CustomerContactBlocked("CUSTOMER_START_AUTHORITY_RESOLVER_UNAVAILABLE")

    def latest_start_or_none(self, scope: TenantScope, batch_id: str) -> CustomerBatchStartDecisionRevision | None:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT authority_data FROM ecommerce_customer_batch_start_decision_revision WHERE org_id=%s AND project_id=%s AND batch_id=%s ORDER BY revision DESC LIMIT 1",
                (*scope.key, batch_id),
            ).fetchone()
        return None if row is None else CustomerBatchStartDecisionRevision.model_validate(row["authority_data"])

    def latest_start_for_tenant_or_none(self, scope: TenantScope) -> CustomerBatchStartDecisionRevision | None:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT authority_data FROM ecommerce_customer_batch_start_decision_revision WHERE org_id=%s AND project_id=%s ORDER BY created_at DESC LIMIT 1",
                scope.key,
            ).fetchone()
        return None if row is None else CustomerBatchStartDecisionRevision.model_validate(row["authority_data"])

    def require_start(self, scope: TenantScope, ref: CustomerExactRef) -> CustomerBatchStartDecisionRevision:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_customer_batch_start_decision_revision WHERE org_id=%s AND project_id=%s AND decision_id=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or f"sha256:{row['content_hash']}" != ref.content_hash:
            raise CustomerContactBlocked("CUSTOMER_START_DECISION_MISSING_OR_DRIFTED")
        return CustomerBatchStartDecisionRevision.model_validate(row["authority_data"])

    def require_action_receipt(self, scope: TenantScope, ref: CustomerExactRef, binding_hash: str) -> None:
        del scope, ref, binding_hash
        raise CustomerContactBlocked("CUSTOMER_ACTION_RECEIPT_RESOLVER_UNAVAILABLE")

    def list_dispatch_observations(self, scope: TenantScope, decision_id: str) -> list[CustomerDispatchObservation]:
        with self._connect(scope) as conn:
            rows = conn.execute(
                "SELECT authority_data FROM ecommerce_customer_dispatch_observation WHERE org_id=%s AND project_id=%s AND decision_id=%s ORDER BY created_at,observation_id",
                (*scope.key, decision_id),
            ).fetchall()
        return [CustomerDispatchObservation.model_validate(row["authority_data"]) for row in rows]

    def authority_counts(self, scope: TenantScope) -> dict[str, int]:
        with self._connect(scope) as conn:
            frequency = conn.execute("SELECT COUNT(*) AS count FROM ecommerce_customer_frequency_policy_revision WHERE org_id=%s AND project_id=%s", scope.key).fetchone()["count"]
            withdrawals = conn.execute("SELECT COUNT(*) AS count FROM ecommerce_customer_consent_withdrawal_observation WHERE org_id=%s AND project_id=%s", scope.key).fetchone()["count"]
        return {"frequency_policy": frequency, "withdrawal": withdrawals}


__all__ = ["EcommerceWorkshopCustomerContactStore"]
