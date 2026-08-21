"""PostgreSQL authority for EffectReviewRevision and EffectMaturity (W-L19)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_effect_review import (
    CreateEffectReviewRequest,
    EffectAxisSnapshot,
    EffectMaturityDecision,
    EffectMaturityStatus,
    EffectReviewRevision,
    EvaluateEffectMaturityRequest,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class AipEffectReviewError(RuntimeError):
    code = "AIP_EFFECT_REVIEW_FAILED"


class AipEffectReviewNotFound(AipEffectReviewError):
    code = "AIP_EFFECT_REVIEW_NOT_FOUND"


class AipEffectReviewConflict(AipEffectReviewError):
    code = "AIP_EFFECT_REVIEW_CONFLICT"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _id(prefix: str, scope: TenantScope, *parts: object) -> str:
    return f"{prefix}-{_hash([scope.org_id, scope.project_id, *parts])[:24]}"


def _tenant(scope: TenantScope) -> TenantContext:
    return TenantContext(org_id=scope.org_id, project_id=scope.project_id)


def _decide_maturity(
    *,
    sample_count: int,
    min_sample: int,
    cutoff_at: datetime,
    observed_at: datetime,
) -> EffectMaturityStatus:
    if sample_count <= 0:
        return EffectMaturityStatus.INSUFFICIENT
    if observed_at < cutoff_at:
        return EffectMaturityStatus.IMMATURE
    if sample_count < min_sample:
        return EffectMaturityStatus.INSUFFICIENT
    return EffectMaturityStatus.MATURE


class AipEffectReviewStore:
    def create_review(
        self,
        scope: TenantScope,
        request: CreateEffectReviewRequest,
        actor: str,
        *,
        now: datetime,
    ) -> EffectReviewRevision:
        if not actor.strip():
            raise ValueError("actor is required")
        with connect(scope) as conn:
            head = conn.execute(
                """SELECT current_revision FROM aip_effect_review_head
                   WHERE org_id=%s AND project_id=%s AND subject_id=%s""",
                (*scope.key, request.subject_id),
            ).fetchone()
            current = 0 if head is None else int(head["current_revision"])
            if request.expected_revision != current:
                raise AipEffectReviewConflict(
                    f"effect review CAS expected={request.expected_revision} current={current}"
                )
            revision = current + 1
            maturity = _decide_maturity(
                sample_count=request.sample_count,
                min_sample=request.min_sample,
                cutoff_at=request.cutoff_at,
                observed_at=now,
            )
            # accepted never forces effect_completed; completion follows maturity only.
            effect_completed = maturity is EffectMaturityStatus.MATURE
            payload = {
                "subjectId": request.subject_id,
                "revision": revision,
                "subjectRef": request.subject_ref.model_dump(mode="json", by_alias=True),
                "observationRefs": [
                    ref.model_dump(mode="json", by_alias=True)
                    for ref in request.observation_refs
                ],
                "metricKeys": request.metric_keys,
                "sampleCount": request.sample_count,
                "minSample": request.min_sample,
                "cutoffAt": request.cutoff_at.isoformat(),
                "eventTimeAt": request.event_time_at.isoformat(),
                "accepted": request.accepted,
                "effectCompleted": effect_completed,
                "maturityStatus": maturity.value,
                "reasonCode": request.reason_code,
            }
            content_hash = _hash(payload)
            review_id = _id("effect-review", scope, request.subject_id, revision)
            conn.execute(
                """INSERT INTO aip_effect_review_revision(
                  org_id,project_id,review_id,subject_id,revision,subject_ref,
                  observation_refs,metric_keys,sample_count,min_sample,cutoff_at,
                  event_time_at,accepted,effect_completed,maturity_status,
                  reason_code,content_hash,actor,created_at)
                  VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,
                         %s,%s,%s,%s,%s,%s,%s)""",
                (
                    *scope.key,
                    review_id,
                    request.subject_id,
                    revision,
                    _json(payload["subjectRef"]),
                    _json(payload["observationRefs"]),
                    _json(request.metric_keys),
                    request.sample_count,
                    request.min_sample,
                    request.cutoff_at,
                    request.event_time_at,
                    request.accepted,
                    effect_completed,
                    maturity.value,
                    request.reason_code,
                    content_hash,
                    actor,
                    now,
                ),
            )
            if head is None:
                conn.execute(
                    """INSERT INTO aip_effect_review_head(
                      org_id,project_id,subject_id,current_revision,version,updated_at)
                      VALUES(%s,%s,%s,%s,1,%s)""",
                    (*scope.key, request.subject_id, revision, now),
                )
            else:
                updated = conn.execute(
                    """UPDATE aip_effect_review_head
                       SET current_revision=%s, version=version+1, updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND subject_id=%s
                         AND current_revision=%s""",
                    (
                        revision,
                        now,
                        *scope.key,
                        request.subject_id,
                        current,
                    ),
                )
                if updated.rowcount != 1:
                    raise AipEffectReviewConflict("effect review head CAS lost")
            conn.commit()
            return self._review_row(
                scope,
                conn.execute(
                    """SELECT * FROM aip_effect_review_revision
                       WHERE org_id=%s AND project_id=%s AND review_id=%s""",
                    (*scope.key, review_id),
                ).fetchone(),
            )

    def get_latest_review(
        self, scope: TenantScope, subject_id: str
    ) -> EffectReviewRevision:
        with connect(scope) as conn:
            row = conn.execute(
                """SELECT r.* FROM aip_effect_review_revision r
                   JOIN aip_effect_review_head h
                     ON h.org_id=r.org_id AND h.project_id=r.project_id
                    AND h.subject_id=r.subject_id AND h.current_revision=r.revision
                   WHERE r.org_id=%s AND r.project_id=%s AND r.subject_id=%s""",
                (*scope.key, subject_id),
            ).fetchone()
            if row is None:
                raise AipEffectReviewNotFound("effect review not found")
            return self._review_row(scope, row)

    def evaluate_maturity(
        self,
        scope: TenantScope,
        request: EvaluateEffectMaturityRequest,
        actor: str,
        *,
        now: datetime,
    ) -> EffectMaturityDecision:
        with connect(scope) as conn:
            review = self.get_latest_review(scope, request.subject_id)
            maturity = _decide_maturity(
                sample_count=review.sample_count,
                min_sample=review.min_sample,
                cutoff_at=review.cutoff_at,
                observed_at=request.observed_at,
            )
            # Re-evaluate completion independently of accept.
            effect_completed = maturity is EffectMaturityStatus.MATURE
            decision_id = _id(
                "effect-maturity",
                scope,
                request.subject_id,
                review.revision,
                request.observed_at.isoformat(),
                request.reason_code,
            )
            conn.execute(
                """INSERT INTO aip_effect_maturity_decision(
                  org_id,project_id,decision_id,subject_id,review_id,review_revision,
                  maturity_status,accepted,effect_completed,sample_count,min_sample,
                  cutoff_at,observed_at,reason_code,actor,created_at)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,decision_id) DO NOTHING""",
                (
                    *scope.key,
                    decision_id,
                    request.subject_id,
                    review.review_id,
                    review.revision,
                    maturity.value,
                    review.accepted,
                    effect_completed,
                    review.sample_count,
                    review.min_sample,
                    review.cutoff_at,
                    request.observed_at,
                    request.reason_code,
                    actor,
                    now,
                ),
            )
            row = conn.execute(
                """SELECT * FROM aip_effect_maturity_decision
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, decision_id),
            ).fetchone()
            conn.commit()
            return EffectMaturityDecision(
                tenant=_tenant(scope),
                decision_id=row["decision_id"],
                subject_id=row["subject_id"],
                review_id=row["review_id"],
                review_revision=row["review_revision"],
                maturity_status=EffectMaturityStatus(row["maturity_status"]),
                accepted=row["accepted"],
                effect_completed=row["effect_completed"],
                sample_count=row["sample_count"],
                min_sample=row["min_sample"],
                cutoff_at=row["cutoff_at"],
                observed_at=row["observed_at"],
                reason_code=row["reason_code"],
                actor=row["actor"],
                created_at=row["created_at"],
            )

    def get_axis_snapshot(
        self, scope: TenantScope, subject_id: str
    ) -> EffectAxisSnapshot:
        with connect(scope) as conn:
            review_row = conn.execute(
                """SELECT r.* FROM aip_effect_review_revision r
                   JOIN aip_effect_review_head h
                     ON h.org_id=r.org_id AND h.project_id=r.project_id
                    AND h.subject_id=r.subject_id AND h.current_revision=r.revision
                   WHERE r.org_id=%s AND r.project_id=%s AND r.subject_id=%s""",
                (*scope.key, subject_id),
            ).fetchone()
            usage = conn.execute(
                """SELECT COUNT(*) AS n FROM aip_usage_receipt
                   WHERE org_id=%s AND project_id=%s""",
                scope.key,
            ).fetchone()
            handoff = conn.execute(
                """SELECT terminal_decision FROM aip_handoff_decision_head
                   WHERE org_id=%s AND project_id=%s AND handoff_id=%s""",
                (*scope.key, subject_id),
            ).fetchone()
            if review_row is None:
                return EffectAxisSnapshot(
                    tenant=_tenant(scope),
                    subject_id=subject_id,
                    usage_settlement=(
                        "has_receipts" if int(usage["n"]) > 0 else "no_receipts"
                    ),
                    handoff_decision=(
                        None if handoff is None else handoff["terminal_decision"]
                    ),
                )
            review = self._review_row(scope, review_row)
            return EffectAxisSnapshot(
                tenant=_tenant(scope),
                subject_id=subject_id,
                item_outcome=None,
                action_outcome=None,
                usage_settlement=(
                    "has_receipts" if int(usage["n"]) > 0 else "no_receipts"
                ),
                effect_maturity=review.maturity_status,
                handoff_decision=(
                    None if handoff is None else handoff["terminal_decision"]
                ),
                accepted=review.accepted,
                effect_completed=review.effect_completed,
                review_revision=review.revision,
            )

    def _review_row(self, scope: TenantScope, row: Any) -> EffectReviewRevision:
        subject_ref = row["subject_ref"]
        if isinstance(subject_ref, str):
            subject_ref = json.loads(subject_ref)
        observations = row["observation_refs"]
        if isinstance(observations, str):
            observations = json.loads(observations)
        metrics = row["metric_keys"]
        if isinstance(metrics, str):
            metrics = json.loads(metrics)
        return EffectReviewRevision(
            tenant=_tenant(scope),
            review_id=row["review_id"],
            subject_id=row["subject_id"],
            revision=row["revision"],
            subject_ref=ResourceRef.model_validate(subject_ref),
            observation_refs=[ResourceRef.model_validate(item) for item in observations],
            metric_keys=list(metrics),
            sample_count=row["sample_count"],
            min_sample=row["min_sample"],
            cutoff_at=row["cutoff_at"],
            event_time_at=row["event_time_at"],
            accepted=row["accepted"],
            effect_completed=row["effect_completed"],
            maturity_status=EffectMaturityStatus(row["maturity_status"]),
            reason_code=row["reason_code"],
            content_hash=row["content_hash"],
            actor=row["actor"],
            created_at=row["created_at"],
        )


__all__ = [
    "AipEffectReviewConflict",
    "AipEffectReviewError",
    "AipEffectReviewNotFound",
    "AipEffectReviewStore",
]
