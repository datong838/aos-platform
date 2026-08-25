"""Append-only PostgreSQL authority for W7-08 media attempt finance."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_media_finance_contracts import (
    BindMediaUsageRequest,
    MediaCancelOutcome,
    MediaCurrencyBucket,
    MediaFeeConclusion,
    MediaFinanceEventKind,
    MediaFinanceListResponse,
    MediaFinanceSnapshot,
    MediaSettlementStatus,
    MediaUsageQuality,
    ObserveMediaCancelRequest,
    PrepareMediaFinanceRequest,
    SettleMediaFinanceRequest,
    TransitionMediaCapacityRequest,
)
from aos_api.aip_media_provider_job_contracts import MediaProviderJob, MediaProviderJobEvent
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


class MediaFinanceError(RuntimeError):
    code = "MEDIA_FINANCE_ERROR"


class MediaFinanceNotFound(MediaFinanceError):
    code = "MEDIA_FINANCE_NOT_FOUND"


class MediaFinanceConflict(MediaFinanceError):
    code = "MEDIA_FINANCE_CONFLICT"


class MediaFinanceDependencyBlocked(MediaFinanceError):
    code = "MEDIA_FINANCE_DEPENDENCY_BLOCKED"


class MediaFinancePersistenceError(MediaFinanceError):
    code = "MEDIA_FINANCE_PERSISTENCE_FAILED"


class AipMediaFinanceStore:
    def __init__(self, *, connect_factory=db_connect) -> None:
        self._connect = connect_factory

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def canonical_hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode()).hexdigest()

    @staticmethod
    def _tenant(scope: TenantScope) -> dict[str, str]:
        return {"orgId": scope.org_id, "projectId": scope.project_id}

    def prepare(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: PrepareMediaFinanceRequest,
        job: MediaProviderJob,
        job_event: MediaProviderJobEvent,
        *,
        now: datetime | None = None,
    ) -> MediaFinanceSnapshot:
        created_at = now or datetime.now(UTC)
        if body.expires_at <= created_at:
            raise MediaFinanceConflict("MEDIA_FINANCE_RESERVATION_EXPIRED")
        if job.sequence != body.expected_job_sequence or job_event.sequence != job.sequence:
            raise MediaFinanceConflict("MEDIA_FINANCE_JOB_SEQUENCE_DRIFTED")
        job_ref = ExactRevisionRef(
            resourceType="MediaProviderJobEvent", resourceId=job.job_id,
            revision=job_event.sequence, contentHash=job_event.event_hash,
        )
        material = {
            "jobRef": job_ref.model_dump(mode="json", by_alias=True),
            "taskRunRef": job.task_run_ref.model_dump(mode="json", by_alias=True),
            "stepRunRef": job.step_run_ref.model_dump(mode="json", by_alias=True),
            "requestFingerprint": job.request_fingerprint,
            "capacityPoolRef": body.capacity_pool_ref.model_dump(mode="json", by_alias=True),
            "budgetRevisionRef": body.budget_revision_ref.model_dump(mode="json", by_alias=True),
            "projectedMinMinor": body.projected_min_minor,
            "projectedMaxMinor": body.projected_max_minor,
            "currency": body.currency,
            "expiresAt": body.expires_at.isoformat(),
        }
        binding_hash = self.canonical_hash(material)
        request_hash = self.canonical_hash({"operation": "prepare", "body": material})
        finance_id = f"media-fin-{uuid.uuid4().hex[:24]}"
        base = {
            **material,
            "financeId": finance_id,
            "attemptBindingHash": binding_hash,
            "capacityReservationRef": {
                "resourceType": "MediaCapacityReservation", "resourceId": f"{finance_id}:capacity",
                "revision": 1, "contentHash": binding_hash,
            },
            "budgetReservationRef": {
                "resourceType": "MediaBudgetReservation", "resourceId": f"{finance_id}:budget",
                "revision": 1, "contentHash": binding_hash,
            },
            "createdBy": actor,
            "createdAt": created_at.isoformat(),
        }
        try:
            with self._connect(scope) as conn:
                replay = self._replay(conn, scope, "prepare", key, request_hash)
                if replay:
                    return self.get(scope, replay["resourceId"], conn=conn)
                self._lock_and_assert_authorities(conn, scope, body)
                existing = conn.execute(
                    "SELECT finance_id FROM aip_media_attempt_finance WHERE org_id=%s AND project_id=%s AND attempt_binding_hash=%s",
                    (*scope.key, binding_hash),
                ).fetchone()
                if existing:
                    raise MediaFinanceConflict("MEDIA_FINANCE_BINDING_ALREADY_RESERVED")
                conn.execute(
                    """INSERT INTO aip_media_attempt_finance(
                       org_id,project_id,finance_id,job_id,attempt_binding_hash,base_payload,created_by,created_at)
                       VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                    (*scope.key, finance_id, job.job_id, binding_hash, self._json(base), actor, created_at),
                )
                self._insert_event(conn, scope, finance_id, 1, MediaFinanceEventKind.PREPARED, {"bindingHash": binding_hash}, actor, created_at)
                self._idempotency(conn, scope, "prepare", key, request_hash, finance_id, 1, binding_hash)
                conn.commit()
                return self.get(scope, finance_id, conn=conn)
        except MediaFinanceError:
            raise
        except Exception as exc:
            raise MediaFinancePersistenceError("media finance prepare failed") from exc

    def append(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        finance_id: str,
        kind: MediaFinanceEventKind,
        body: ObserveMediaCancelRequest | TransitionMediaCapacityRequest | BindMediaUsageRequest | SettleMediaFinanceRequest,
    ) -> MediaFinanceSnapshot:
        payload = body.model_dump(mode="json", by_alias=True)
        expected_version = body.expected_version
        request_hash = self.canonical_hash({"financeId": finance_id, "kind": kind.value, "body": payload})
        try:
            with self._connect(scope) as conn:
                replay = self._replay(conn, scope, kind.value, key, request_hash)
                if replay:
                    return self.get(scope, replay["resourceId"], conn=conn)
                current = self.get(scope, finance_id, conn=conn)
                if current.version != expected_version:
                    raise MediaFinanceConflict("MEDIA_FINANCE_VERSION_CONFLICT")
                self._assert_event(current, kind, body)
                version = expected_version + 1
                event_hash = self._insert_event(conn, scope, finance_id, version, kind, payload, actor, body.observed_at)
                self._idempotency(conn, scope, kind.value, key, request_hash, finance_id, version, event_hash)
                conn.commit()
                return self.get(scope, finance_id, conn=conn)
        except MediaFinanceError:
            raise
        except Exception as exc:
            raise MediaFinancePersistenceError("media finance event persistence failed") from exc

    def get(self, scope: TenantScope, finance_id: str, *, conn: Any | None = None) -> MediaFinanceSnapshot:
        def read(connection: Any) -> MediaFinanceSnapshot:
            row = connection.execute(
                "SELECT base_payload FROM aip_media_attempt_finance WHERE org_id=%s AND project_id=%s AND finance_id=%s",
                (*scope.key, finance_id),
            ).fetchone()
            if row is None:
                raise MediaFinanceNotFound(finance_id)
            events = connection.execute(
                """SELECT version,event_kind,payload,content_hash,actor,created_at
                   FROM aip_media_attempt_finance_event
                   WHERE org_id=%s AND project_id=%s AND finance_id=%s ORDER BY version""",
                (*scope.key, finance_id),
            ).fetchall()
            return self._reduce(scope, self._load(row["base_payload"]), events)

        if conn is not None:
            return read(conn)
        with self._connect(scope) as connection:
            return read(connection)

    def get_for_job(self, scope: TenantScope, job_id: str, *, conn: Any | None = None) -> MediaFinanceSnapshot:
        def read(connection: Any) -> MediaFinanceSnapshot:
            row = connection.execute(
                """SELECT finance_id FROM aip_media_attempt_finance
                   WHERE org_id=%s AND project_id=%s AND job_id=%s ORDER BY created_at DESC LIMIT 1""",
                (*scope.key, job_id),
            ).fetchone()
            if row is None:
                raise MediaFinanceNotFound(job_id)
            return self.get(scope, row["finance_id"], conn=connection)
        if conn is not None:
            return read(conn)
        with self._connect(scope) as connection:
            return read(connection)

    def list(self, scope: TenantScope, *, limit: int = 100) -> MediaFinanceListResponse:
        if not 1 <= limit <= 100:
            raise MediaFinanceConflict("MEDIA_FINANCE_LIMIT_INVALID")
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT finance_id FROM aip_media_attempt_finance
                   WHERE org_id=%s AND project_id=%s ORDER BY created_at DESC,finance_id LIMIT %s""",
                (*scope.key, limit),
            ).fetchall()
            items = [self.get(scope, row["finance_id"], conn=conn) for row in rows]
            return MediaFinanceListResponse(tenant=self._tenant(scope), items=items, count=len(items))

    def require_submit_ready(self, scope: TenantScope, job: MediaProviderJob) -> None:
        try:
            snapshot = self.get_for_job(scope, job.job_id)
        except MediaFinanceNotFound as exc:
            raise MediaFinanceDependencyBlocked("MEDIA_DUAL_RESERVATION_REQUIRED") from exc
        if snapshot.job_ref.revision != job.sequence:
            raise MediaFinanceDependencyBlocked("MEDIA_FINANCE_JOB_SEQUENCE_DRIFTED")
        if not snapshot.reservations_active or snapshot.expires_at <= datetime.now(UTC):
            raise MediaFinanceDependencyBlocked("MEDIA_DUAL_RESERVATION_INACTIVE")
        if snapshot.settlement_status is not MediaSettlementStatus.PENDING:
            raise MediaFinanceDependencyBlocked("MEDIA_FINANCE_ALREADY_SETTLED")

    @staticmethod
    def _assert_event(snapshot: MediaFinanceSnapshot, kind: MediaFinanceEventKind, body: Any) -> None:
        if kind is MediaFinanceEventKind.USAGE_BOUND:
            identities = {(ref.resource_id, ref.revision, ref.content_hash) for ref in snapshot.usage_receipt_refs}
            ref = body.usage_receipt_ref
            if (ref.resource_id, ref.revision, ref.content_hash) in identities:
                raise MediaFinanceConflict("MEDIA_USAGE_RECEIPT_ALREADY_BOUND")
            supersedes = body.supersedes_usage_receipt_ref
            if supersedes and (supersedes.resource_id, supersedes.revision, supersedes.content_hash) not in identities:
                raise MediaFinanceConflict("MEDIA_USAGE_SUPERSEDES_REF_NOT_BOUND")
        if kind in {MediaFinanceEventKind.CAPACITY_CONSUMED, MediaFinanceEventKind.CAPACITY_RELEASED} and not snapshot.reservations_active:
            raise MediaFinanceConflict("MEDIA_DUAL_RESERVATION_INACTIVE")
        if kind is MediaFinanceEventKind.SETTLED:
            if snapshot.settlement_status is not MediaSettlementStatus.PENDING:
                raise MediaFinanceConflict("MEDIA_SETTLEMENT_ALREADY_DECIDED")
            if body.status is MediaSettlementStatus.SETTLED and any(bucket.unknown_count for bucket in snapshot.currency_buckets):
                raise MediaFinanceDependencyBlocked("MEDIA_USAGE_UNKNOWN_RECONCILE_REQUIRED")

    def _insert_event(self, conn: Any, scope: TenantScope, finance_id: str, version: int, kind: MediaFinanceEventKind, payload: dict[str, Any], actor: str, created_at: datetime) -> str:
        content_hash = self.canonical_hash({"financeId": finance_id, "version": version, "kind": kind.value, "payload": payload})
        conn.execute(
            """INSERT INTO aip_media_attempt_finance_event(
               org_id,project_id,finance_id,version,event_kind,payload,content_hash,actor,created_at)
               VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
            (*scope.key, finance_id, version, kind.value, self._json(payload), content_hash, actor, created_at),
        )
        return content_hash

    def _lock_and_assert_authorities(self, conn: Any, scope: TenantScope, body: PrepareMediaFinanceRequest) -> None:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"media-capacity:{scope.org_id}:{scope.project_id}:{body.capacity_pool_ref.resource_id}",))
        capacity = conn.execute(
            """SELECT max_concurrency,lifecycle FROM aip_model_capacity_pool_revision
               WHERE org_id=%s AND project_id=%s AND pool_id=%s AND revision=%s AND content_hash=%s""",
            (*scope.key, body.capacity_pool_ref.resource_id, body.capacity_pool_ref.revision, body.capacity_pool_ref.content_hash),
        ).fetchone()
        if capacity is None or capacity["lifecycle"] != "active":
            raise MediaFinanceDependencyBlocked("MEDIA_CAPACITY_POOL_REF_BLOCKED")
        active_capacity = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_media_attempt_finance f
               WHERE f.org_id=%s AND f.project_id=%s
                 AND f.base_payload->'capacityPoolRef'->>'resourceId'=%s
                 AND (f.base_payload->'capacityPoolRef'->>'revision')::BIGINT=%s
                 AND f.base_payload->'capacityPoolRef'->>'contentHash'=%s
                 AND (f.base_payload->>'expiresAt')::TIMESTAMPTZ>NOW()
                 AND NOT EXISTS (SELECT 1 FROM aip_media_attempt_finance_event e
                   WHERE e.org_id=f.org_id AND e.project_id=f.project_id AND e.finance_id=f.finance_id
                     AND e.event_kind='capacity_released')""",
            (*scope.key, body.capacity_pool_ref.resource_id, body.capacity_pool_ref.revision, body.capacity_pool_ref.content_hash),
        ).fetchone()["count"]
        if int(active_capacity) >= int(capacity["max_concurrency"]):
            raise MediaFinanceDependencyBlocked("MEDIA_CAPACITY_CONCURRENCY_EXHAUSTED")

        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"media-budget:{scope.org_id}:{scope.project_id}:{body.budget_revision_ref.resource_id}",))
        budget = conn.execute(
            """SELECT daily_limit_minor,currency,lifecycle,effective_from,effective_until
               FROM aip_budget_revision WHERE org_id=%s AND project_id=%s AND budget_id=%s
                 AND revision=%s AND content_hash=%s""",
            (*scope.key, body.budget_revision_ref.resource_id, body.budget_revision_ref.revision, body.budget_revision_ref.content_hash),
        ).fetchone()
        if budget is None or budget["lifecycle"] != "active" or budget["currency"] != body.currency or not (budget["effective_from"] <= datetime.now(UTC) < budget["effective_until"]):
            raise MediaFinanceDependencyBlocked("MEDIA_BUDGET_REVISION_REF_BLOCKED")
        exposure = conn.execute(
            """SELECT COALESCE(SUM((f.base_payload->>'projectedMaxMinor')::BIGINT),0) AS total
               FROM aip_media_attempt_finance f
               WHERE f.org_id=%s AND f.project_id=%s
                 AND f.base_payload->'budgetRevisionRef'->>'resourceId'=%s
                 AND (f.base_payload->'budgetRevisionRef'->>'revision')::BIGINT=%s
                 AND f.base_payload->'budgetRevisionRef'->>'contentHash'=%s
                 AND f.base_payload->>'currency'=%s
                 AND (f.base_payload->>'expiresAt')::TIMESTAMPTZ>NOW()
                 AND NOT EXISTS (SELECT 1 FROM aip_media_attempt_finance_event e
                   WHERE e.org_id=f.org_id AND e.project_id=f.project_id AND e.finance_id=f.finance_id
                     AND e.event_kind='settled')""",
            (*scope.key, body.budget_revision_ref.resource_id, body.budget_revision_ref.revision, body.budget_revision_ref.content_hash, body.currency),
        ).fetchone()["total"]
        if int(exposure) + body.projected_max_minor > int(budget["daily_limit_minor"]):
            raise MediaFinanceDependencyBlocked("MEDIA_BUDGET_EXPOSURE_EXHAUSTED")

    def _replay(self, conn: Any, scope: TenantScope, operation: str, key: str, request_hash: str) -> dict[str, Any] | None:
        row = conn.execute(
            """SELECT request_hash,result_ref FROM aip_media_attempt_finance_idempotency
               WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s""",
            (*scope.key, operation, key),
        ).fetchone()
        if row and row["request_hash"] != request_hash:
            raise MediaFinanceConflict("MEDIA_FINANCE_IDEMPOTENCY_CONFLICT")
        return self._load(row["result_ref"]) if row else None

    def _idempotency(self, conn: Any, scope: TenantScope, operation: str, key: str, request_hash: str, finance_id: str, revision: int, content_hash: str) -> None:
        conn.execute(
            """INSERT INTO aip_media_attempt_finance_idempotency(
               org_id,project_id,operation,idempotency_key,request_hash,result_ref)
               VALUES(%s,%s,%s,%s,%s,%s::jsonb)""",
            (*scope.key, operation, key, request_hash, self._json({"resourceType": "MediaFinanceEvent", "resourceId": finance_id, "revision": revision, "contentHash": content_hash})),
        )

    def _reduce(self, scope: TenantScope, base: dict[str, Any], rows: list[Any]) -> MediaFinanceSnapshot:
        buckets: dict[str, dict[str, int]] = {}
        usage_items: list[dict[str, Any]] = []
        active = True
        cancel_outcome = None
        fee = MediaFeeConclusion.UNKNOWN
        usage_refs: list[ExactRevisionRef] = []
        settlement = MediaSettlementStatus.PENDING
        decision = None
        updated_at = datetime.fromisoformat(base["createdAt"])
        for row in rows:
            kind = MediaFinanceEventKind(row["event_kind"])
            payload = self._load(row["payload"])
            updated_at = row["created_at"]
            if kind is MediaFinanceEventKind.CAPACITY_RELEASED:
                active = False
            elif kind is MediaFinanceEventKind.CANCEL_OBSERVED:
                cancel_outcome = MediaCancelOutcome(payload["outcome"])
                fee = MediaFeeConclusion(payload["feeConclusion"])
            elif kind is MediaFinanceEventKind.USAGE_BOUND:
                ref = ExactRevisionRef.model_validate(payload["usageReceiptRef"])
                usage_refs.append(ref)
                supersedes = payload.get("supersedesUsageReceiptRef")
                if supersedes:
                    superseded = ExactRevisionRef.model_validate(supersedes)
                    for item in usage_items:
                        if item["ref"] == superseded:
                            item["active"] = False
                usage_items.append({"ref": ref, "payload": payload, "active": True})
            elif kind is MediaFinanceEventKind.SETTLED:
                settlement = MediaSettlementStatus(payload["status"])
                decision = ExactRevisionRef.model_validate(payload["decisionRef"])
        for item in usage_items:
            if not item["active"]:
                continue
            payload = item["payload"]
            bucket = buckets.setdefault(payload["currency"], {"measured": 0, "estimated": 0, "unknown": 0, "adjustment": 0, "refund": 0})
            quality = MediaUsageQuality(payload["quality"])
            if quality is MediaUsageQuality.UNKNOWN:
                bucket["unknown"] += 1
            else:
                bucket[quality.value] += int(payload["amountMinor"])
        if settlement is not MediaSettlementStatus.PENDING:
            bucket = buckets.setdefault(base["currency"], {"measured": 0, "estimated": 0, "unknown": 0, "adjustment": 0, "refund": 0})
            settlement_payload = next(self._load(row["payload"]) for row in reversed(rows) if MediaFinanceEventKind(row["event_kind"]) is MediaFinanceEventKind.SETTLED)
            bucket["adjustment"] += int(settlement_payload["adjustmentMinor"])
            bucket["refund"] += int(settlement_payload["refundMinor"])
        blocker_codes: list[str] = []
        if datetime.fromisoformat(base["expiresAt"]) <= datetime.now(UTC) or not active:
            blocker_codes.append("MEDIA_DUAL_RESERVATION_INACTIVE")
        if any(item["unknown"] for item in buckets.values()):
            blocker_codes.append("MEDIA_USAGE_UNKNOWN_RECONCILE_REQUIRED")
        if cancel_outcome is MediaCancelOutcome.UNKNOWN or fee is MediaFeeConclusion.UNKNOWN:
            blocker_codes.append("MEDIA_CANCEL_FEE_UNKNOWN")
        if settlement is MediaSettlementStatus.PENDING:
            blocker_codes.append("MEDIA_SETTLEMENT_PENDING")
        currency_buckets = []
        for currency, item in sorted(buckets.items()):
            net = item["measured"] + item["estimated"] + item["adjustment"] - item["refund"]
            residual = None if item["unknown"] else net - (base["projectedMaxMinor"] if currency == base["currency"] else 0)
            currency_buckets.append(MediaCurrencyBucket(currency=currency, measuredMinor=item["measured"], estimatedMinor=item["estimated"], unknownCount=item["unknown"], adjustmentMinor=item["adjustment"], refundMinor=item["refund"], residualMinor=residual))
        return MediaFinanceSnapshot(
            tenant=self._tenant(scope), financeId=base["financeId"], version=int(rows[-1]["version"]),
            jobRef=base["jobRef"], taskRunRef=base["taskRunRef"], stepRunRef=base["stepRunRef"],
            capacityPoolRef=base["capacityPoolRef"], capacityReservationRef=base["capacityReservationRef"],
            budgetRevisionRef=base["budgetRevisionRef"], budgetReservationRef=base["budgetReservationRef"],
            attemptBindingHash=base["attemptBindingHash"], projectedMinMinor=base["projectedMinMinor"],
            projectedMaxMinor=base["projectedMaxMinor"], projectedCurrency=base["currency"],
            reservationsActive=active and datetime.fromisoformat(base["expiresAt"]) > datetime.now(UTC),
            cancelOutcome=cancel_outcome, feeConclusion=fee, usageReceiptRefs=usage_refs,
            currencyBuckets=currency_buckets, settlementStatus=settlement, settlementDecisionRef=decision,
            blockerCodes=blocker_codes, expiresAt=base["expiresAt"], createdBy=base["createdBy"],
            createdAt=base["createdAt"], updatedAt=updated_at, externalEffectsAllowed=False,
        )

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value


__all__ = [name for name in globals() if name.startswith("Aip") or name.startswith("Media")]
