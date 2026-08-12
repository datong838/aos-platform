"""Fail-closed governance service for AIP-5 memory promotion.

The service owns governance decisions.  ``AipMemoryStore`` remains the
tenant-scoped persistence primitive and must not be exposed as an approval API.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_memory_contracts import (
    ArtifactGovernanceInspection,
    ArtifactPiiStatus,
    GovernanceApprovalRef,
    KnowledgeSourceRef,
    LicensePolicyDecision,
    MemoryCandidate,
    MemoryCandidateStatus,
    MemoryItem,
    MemoryItemRevision,
)
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ArtifactInspector = Callable[
    [TenantScope, ArtifactRef], ArtifactGovernanceInspection
]
LicenseResolver = Callable[
    [TenantScope, KnowledgeSourceRef], LicensePolicyDecision
]


class AipMemoryGovernanceBlocked(RuntimeError):
    code = "AIP_MEMORY_GOVERNANCE_BLOCKED"

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__(", ".join(reasons))


class AipMemoryGovernanceService:
    def __init__(
        self,
        *,
        artifact_inspector: ArtifactInspector,
        license_resolver: LicenseResolver,
        store: AipMemoryStore | None = None,
        connect_factory=None,
    ) -> None:
        self._artifact_inspector = artifact_inspector
        self._license_resolver = license_resolver
        self._store = store or AipMemoryStore(connect_factory)
        self._connect_factory = connect_factory or db_connect

    def approve_candidate(
        self,
        scope: TenantScope,
        candidate_id: str,
        *,
        expected_version: int,
        governance: GovernanceApprovalRef,
        required_applicability: list[str],
        actor: str,
        occurred_at: datetime,
    ) -> MemoryCandidate:
        candidate = self._store.get_candidate(scope, candidate_id)
        if candidate.status not in {
            MemoryCandidateStatus.PENDING,
            MemoryCandidateStatus.QUARANTINED,
        }:
            raise AipMemoryGovernanceBlocked(["candidate_terminal"])
        reasons = self._gate_reasons(
            scope,
            candidate,
            required_applicability=required_applicability,
            governance=governance,
            occurred_at=occurred_at,
        )
        if reasons:
            if candidate.status is MemoryCandidateStatus.QUARANTINED:
                raise AipMemoryGovernanceBlocked(reasons)
            return self._store.transition_candidate(
                scope,
                candidate_id,
                to_status=MemoryCandidateStatus.QUARANTINED,
                expected_version=expected_version,
                actor=actor,
                occurred_at=occurred_at,
                reason_codes=reasons,
            )
        return self._store.transition_candidate(
            scope,
            candidate_id,
            to_status=MemoryCandidateStatus.APPROVED,
            expected_version=expected_version,
            actor=actor,
            occurred_at=occurred_at,
            governance=governance,
        )

    def promote_candidate(
        self,
        scope: TenantScope,
        candidate_id: str,
        *,
        memory_item_id: str,
        expected_version: int,
        required_applicability: list[str],
        actor: str,
        occurred_at: datetime,
        expires_at: datetime | None = None,
    ) -> tuple[MemoryCandidate, MemoryItem, MemoryItemRevision]:
        candidate = self._store.get_candidate(scope, candidate_id)
        if candidate.status is not MemoryCandidateStatus.APPROVED:
            raise AipMemoryGovernanceBlocked(["candidate_not_approved"])
        if candidate.governance is None:
            raise AipMemoryGovernanceBlocked(["approval_authority_invalid"])
        reasons = self._gate_reasons(
            scope,
            candidate,
            required_applicability=required_applicability,
            governance=candidate.governance,
            occurred_at=occurred_at,
        )
        if reasons:
            raise AipMemoryGovernanceBlocked(reasons)
        return self._store.promote_candidate(
            scope,
            candidate_id,
            memory_item_id=memory_item_id,
            expected_version=expected_version,
            actor=actor,
            occurred_at=occurred_at,
            expires_at=expires_at,
        )

    def _gate_reasons(
        self,
        scope: TenantScope,
        candidate: MemoryCandidate,
        *,
        required_applicability: list[str],
        governance: GovernanceApprovalRef,
        occurred_at: datetime,
    ) -> list[str]:
        reasons: list[str] = []
        if not scope.org_id.strip() or not scope.project_id.strip():
            reasons.append("tenant_scope_invalid")
        inspection = self._inspect(scope, candidate.request.payload)
        if inspection is None:
            reasons.append("source_artifact_unverified")
        elif inspection.artifact != candidate.request.payload:
            reasons.append("source_hash_mismatch")
        elif inspection.pii_status == ArtifactPiiStatus.CONTAINS_PII:
            reasons.append("pii_detected")
        elif inspection.pii_status == ArtifactPiiStatus.UNKNOWN:
            reasons.append("pii_status_unknown")

        license_decision = self._license(scope, candidate.request.source)
        if license_decision == LicensePolicyDecision.DENIED:
            reasons.append("license_denied")
        elif license_decision == LicensePolicyDecision.UNKNOWN:
            reasons.append("license_status_unknown")

        if candidate.request.source.freshness_expires_at <= occurred_at:
            reasons.append("source_stale")
        wanted = {value.strip() for value in required_applicability if value.strip()}
        if not wanted:
            reasons.append("applicability_missing")
        elif not wanted.issubset(set(candidate.request.source.applicability)):
            reasons.append("applicability_mismatch")

        reasons.extend(self._canonical_conflicts(scope, candidate))
        reasons.extend(self._authority_reasons(scope, governance, occurred_at))
        return list(dict.fromkeys(reasons))

    def _inspect(
        self, scope: TenantScope, artifact: ArtifactRef
    ) -> ArtifactGovernanceInspection | None:
        try:
            return self._artifact_inspector(scope, artifact)
        except Exception:
            return None

    def _license(
        self, scope: TenantScope, source: KnowledgeSourceRef
    ) -> LicensePolicyDecision:
        try:
            return LicensePolicyDecision(self._license_resolver(scope, source))
        except Exception:
            return LicensePolicyDecision.UNKNOWN

    def _canonical_conflicts(
        self, scope: TenantScope, candidate: MemoryCandidate
    ) -> list[str]:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT r.content_hash
                   FROM aip_memory_item i
                   JOIN aip_memory_item_revision r
                     ON r.org_id=i.org_id AND r.project_id=i.project_id
                    AND r.memory_item_id=i.memory_item_id
                    AND r.revision=i.current_revision
                   WHERE i.org_id=%s AND i.project_id=%s
                     AND i.status='active' AND i.scope=%s
                     AND i.subject_ref=%s::jsonb""",
                (
                    *scope.key,
                    candidate.scope.value,
                    AipMemoryStore._json(candidate.request.subject),
                ),
            ).fetchall()
        if not rows:
            return []
        if any(row["content_hash"] == candidate.request.payload.content_hash for row in rows):
            return ["duplicate_memory"]
        return ["memory_conflict"]

    def _authority_reasons(
        self,
        scope: TenantScope,
        governance: GovernanceApprovalRef,
        occurred_at: datetime,
    ) -> list[str]:
        eval_revision = self._positive_int(governance.eval_report.revision)
        draft_revision = self._positive_int(governance.draft.revision)
        approval_revision = self._positive_int(governance.approval_event.revision)
        reasons: list[str] = []
        if governance.eval_report.artifact_type != "eval_report":
            reasons.append("eval_authority_invalid")
        if (
            governance.draft.authority != "postgresql"
            or governance.draft.resource_type != "aip.draft"
        ):
            reasons.append("draft_authority_invalid")
        if (
            governance.approval_event.authority != "postgresql"
            or governance.approval_event.resource_type != "aip.approval_event"
        ):
            reasons.append("approval_authority_invalid")
        with self._connect_factory(scope) as conn:
            eval_row = None
            if eval_revision is not None:
                eval_row = conn.execute(
                    """SELECT gate_passed FROM aip_eval_report_revision
                       WHERE org_id=%s AND project_id=%s AND report_id=%s
                         AND revision=%s AND content_hash=%s""",
                    (
                        *scope.key,
                        governance.eval_report.artifact_id,
                        eval_revision,
                        governance.eval_report.content_hash,
                    ),
                ).fetchone()
            if eval_row is None or not eval_row["gate_passed"]:
                reasons.append("eval_authority_invalid")

            draft_row = None
            if draft_revision is not None:
                draft_row = conn.execute(
                    """SELECT proposal_id,proposal_version,proposal_hash,status
                       FROM aip_action_draft
                       WHERE org_id=%s AND project_id=%s AND draft_id=%s""",
                    (*scope.key, governance.draft.resource_id),
                ).fetchone()
            if (
                draft_row is None
                or draft_row["status"] != "approved"
                or int(draft_row["proposal_version"]) != draft_revision
            ):
                reasons.append("draft_authority_invalid")

            approval_row = None
            if approval_revision is not None:
                approval_row = conn.execute(
                    """SELECT proposal_id,proposal_version,proposal_hash,decision,
                              expires_at
                       FROM aip_action_approval_event
                       WHERE org_id=%s AND project_id=%s
                         AND approval_event_id=%s""",
                    (*scope.key, governance.approval_event.resource_id),
                ).fetchone()
            if (
                approval_row is None
                or approval_row["decision"] != "approved"
                or int(approval_row["proposal_version"]) != approval_revision
                or (
                    approval_row["expires_at"] is not None
                    and approval_row["expires_at"] <= occurred_at
                )
                or draft_row is None
                or approval_row["proposal_id"] != draft_row["proposal_id"]
                or approval_row["proposal_version"] != draft_row["proposal_version"]
                or approval_row["proposal_hash"] != draft_row["proposal_hash"]
            ):
                reasons.append("approval_authority_invalid")
        return reasons

    @staticmethod
    def _positive_int(value: str | None) -> int | None:
        try:
            parsed = int(value or "")
        except ValueError:
            return None
        return parsed if parsed >= 1 else None


__all__ = [
    "AipMemoryGovernanceBlocked",
    "AipMemoryGovernanceService",
    "ArtifactInspector",
    "LicenseResolver",
]
