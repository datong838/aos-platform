"""Read one claimed DataRequirement Outbox back to its original analysis route."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from psycopg.types.json import Jsonb

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_outbox_store import DataRequirementOutboxClaim
from aos_api.data_requirement_store import DataRequirementStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    AnalysisAdvanceHostService,
    TransactionBoundConnectFactory,
    _HostAnalysisReceiptStore,
    _occurrence_payload,
)
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_locator import PipelineSnapshotGroupLocator
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class AnalysisDataRequirementRoute:
    requirement: DataRequirementRevisionRecord
    analysis_receipt_ref: dict
    occurrence_id: str
    actor: str
    source_run_id: str
    source_control_ref: PipelineExactRef
    group_id: str
    group_bindings: tuple[tuple[PipelineExactRef, str], ...]
    installation_id: str
    generation: str


class AnalysisDataRequirementRouteReader:
    """Resolve immutable lineage only; this object grants no data or Run action."""

    def __init__(self, *, claims, connect_factory):
        if type(claims) is not PipelineSourceClaimOwner or not callable(connect_factory):
            raise TypeError("exact source claims and connection factory required")
        self._claims = claims
        self._connect = connect_factory
        self._groups = PipelineSnapshotGroupLocator(claims=claims)

    @staticmethod
    def _validate_claim(claim):
        if type(claim) is not DataRequirementOutboxClaim:
            raise TypeError("exact claimed DataRequirement Outbox required")
        expected = {
            "eventId": claim.event_id,
            "requirementId": claim.requirement_id,
            "revision": claim.requirement_revision,
            "contentHash": claim.content_hash,
        }
        if claim.topic != "data.requirement.request" or claim.payload != expected:
            raise ValueError("DataRequirement Outbox payload differs from its claim")

    @staticmethod
    def _outbox_current(conn, scope, claim, *, expected_state):
        row = conn.execute(
            """SELECT o.requirement_id,o.requirement_revision,o.event_id,o.topic,o.payload,
                      o.content_hash,d.state,d.attempt,d.lease_token,d.lease_expires_at,
                      d.lease_expires_at>clock_timestamp() AS lease_current
                 FROM public.data_requirement_outbox o
                 JOIN public.data_requirement_outbox_delivery d
                   USING(org_id,project_id,outbox_id)
                WHERE o.org_id=%s AND o.project_id=%s AND o.outbox_id=%s""",
            (*scope.key, claim.outbox_id),
        ).fetchone()
        if (
            row is None
            or row["requirement_id"] != claim.requirement_id
            or int(row["requirement_revision"]) != claim.requirement_revision
            or row["event_id"] != claim.event_id
            or row["topic"] != claim.topic
            or row["payload"] != claim.payload
            or "sha256:" + str(row["content_hash"]).strip() != claim.content_hash
            or row["state"] != expected_state
            or int(row["attempt"]) != claim.attempt
            or row["lease_token"] != claim.lease_token
            or row["lease_expires_at"] != claim.lease_expires_at
            or (expected_state == "claimed" and row["lease_current"] is not True)
        ):
            raise ValueError("DataRequirement Outbox claim is no longer current")

    @staticmethod
    def _analysis_receipt(tx, scope, requirement):
        run_ref = requirement.run_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
        rows = tx.execute(
            """SELECT target_receipt_ref,response
                 FROM public.ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_analysis_advance'
                  AND response->'runRef'=%s::jsonb
                  AND response->>'phase'='PREPARING'
                  AND response->'completed'='false'::jsonb
                  AND response->'requirementRef'='null'::jsonb""",
            (*scope.key, Jsonb(run_ref)),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("DataRequirement original AnalysisRuntimeReceipt is not unique")
        row = rows[0]
        reference = row["target_receipt_ref"]
        saved = _HostAnalysisReceiptStore(tx, scope).read_exact(reference)
        if (
            saved is None
            or saved != row["response"]
            or saved.get("receiptRef") != reference
            or saved.get("phase") != "PREPARING"
            or saved.get("completed") is not False
            or saved.get("runRef") != run_ref
            or saved.get("caseRef")
            != requirement.case_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            or saved.get("cutoffAt") != requirement.cutoff_at.isoformat()
            or saved.get("requirementRef") is not None
        ):
            raise ValueError("DataRequirement original AnalysisRuntimeReceipt differs")
        InvestigationExactRef.model_validate(reference)
        return saved

    def _read(self, scope, claim, *, expected_state):
        if type(scope) is not TenantScope:
            raise TypeError("exact DataRequirement route tenant required")
        self._validate_claim(claim)
        with self._connect(scope) as conn:
            tx = HostTransaction(conn)
            self._outbox_current(conn, scope, claim, expected_state=expected_state)
            factory = TransactionBoundConnectFactory(tx, scope)
            reference = InvestigationExactRef(
                resource_type="DataRequirementRevision",
                resource_id=claim.requirement_id,
                revision=claim.requirement_revision,
                content_hash=claim.content_hash,
            )
            requirements = DataRequirementStore(factory)
            requirement = requirements.get_exact(scope, reference)
            if requirements.get_current(scope, claim.requirement_id) != requirement:
                raise ValueError("DataRequirement Outbox revision is no longer current")
            if requirement.status.value != "requested" or requirement.blockers:
                raise ValueError("DataRequirement Outbox is not an actionable request")
            root = self._analysis_receipt(tx, scope, requirement)
            occurrence_id = UUID(root["occurrenceRef"]["resourceId"])
            occurrence = _occurrence_payload(tx, scope, occurrence_id)
            historical = AnalysisAdvanceHostService._accepted_occurrence_reference(
                tx, scope, occurrence
            )
            if (
                occurrence["status"] != "accepted"
                or occurrence["triggerSource"] != "event"
                or occurrence["operationId"] != "ecommerce_growth_analysis_advance"
                or historical != root["occurrenceRef"]
            ):
                raise ValueError("DataRequirement original occurrence differs")
            from aos_api.ecommerce_product_event_origin import ProductEventOriginStore

            origin = ProductEventOriginStore(tx, scope).read(occurrence_id)
            if origin is None:
                raise ValueError("DataRequirement original ProductEvent route is missing")
            group = self._groups.read(
                conn,
                scope=scope,
                run_id=origin["runId"],
                expected_cutoff=requirement.cutoff_at,
            )
            if group is None or group.actor != origin["actor"]:
                raise ValueError("DataRequirement original snapshot group differs")
            matches = [(control, run_id) for control, run_id in group.bindings if run_id == origin["runId"]]
            if len(matches) != 1:
                raise ValueError("DataRequirement source run is not unique in its snapshot group")
            control_ref, source_run_id = matches[0]
            return AnalysisDataRequirementRoute(
                requirement=requirement,
                analysis_receipt_ref=root["receiptRef"],
                occurrence_id=str(occurrence_id),
                actor=origin["actor"],
                source_run_id=source_run_id,
                source_control_ref=control_ref,
                group_id=group.group_id,
                group_bindings=group.bindings,
                installation_id=occurrence["installationId"],
                generation=occurrence["generation"],
            )

    def read(self, scope, claim):
        return self._read(scope, claim, expected_state="claimed")

    def read_unknown(self, scope, claim):
        """Rebuild only the immutable route of the same unknown delivery attempt."""
        return self._read(scope, claim, expected_state="unknown")
