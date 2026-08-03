"""PostgreSQL truth store for M4 Integration Cases and canonical Evidence."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable, Iterable, Sequence
from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import psycopg
from psycopg import errors
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    EvidenceIntegrityCorruptError,
    EvidenceReferenceInvalidError,
    IdempotencyConflictError,
    RevisionConflictError,
)
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_EVIDENCE_ADAPTER,
    STAGE_POLICY_VERSION,
    CreateIntegrationCaseRequest,
    IntegrationEvidenceEnvelope,
    IntegrationEvidenceSnapshotResponse,
    IntegrationStage,
    IntegrationStageEvent,
)
from aos_api.asset_registry.integration_stage_policy import (
    PlannedBasis,
    StagePolicyResult,
    evaluate_contract_stage_policy,
)
from aos_api.db import connect

JsonObject = dict[str, Any]
ConnectFactory = Callable[[], AbstractContextManager[Any]]
UuidFactory = Callable[[], uuid.UUID]
Clock = Callable[[], datetime]
CommandHandler = Callable[[Any], "IntegrationCommandResult"]
_STRONG_ETAG = re.compile(r'^"[1-9][0-9]*"$')


class IntegrationPersistenceError(RuntimeError):
    """Safe failure used when PostgreSQL details must not escape the Store."""

    def __init__(self) -> None:
        super().__init__("integration case persistence failed")


@dataclass(frozen=True, slots=True)
class IntegrationCommandResult:
    case_pk: uuid.UUID
    status_code: int
    response_json: JsonObject
    response_etag: str


@dataclass(frozen=True, slots=True)
class IntegrationCommandReceipt(IntegrationCommandResult):
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class StoredIntegrationCase:
    org_id: str
    project_id: str
    case_pk: uuid.UUID
    case_id: str
    instance_pk: uuid.UUID
    scope: Literal["current", "reference"]
    display_name: str
    owner: str | None
    required_markings: tuple[str, ...]
    current_revision: int
    etag_version: int
    installation_pk: uuid.UUID | None
    installation_id: str | None
    installation_revision: int | None
    composition_pk: uuid.UUID | None
    composition_id: str | None
    lock_revision: int | None
    lock_hash: str | None
    overlay_revision: str | None
    snapshot_revision: int
    computed_stage: IntegrationStage
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectionMetrics:
    connector_count: int | None
    pipeline_count: int | None
    dataset_row_count: int | None
    latency_ms: int | None


@dataclass(frozen=True, slots=True)
class ProjectionSnapshot:
    response: IntegrationEvidenceSnapshotResponse
    stage_event: IntegrationStageEvent | None
    metrics: ProjectionMetrics


class PostgresIntegrationStore:
    """Persist one canonical Case mutation as one serial PostgreSQL transaction."""

    def __init__(
        self,
        connect_factory: ConnectFactory = connect,
        *,
        uuid_factory: UuidFactory = uuid.uuid4,
        clock: Clock | None = None,
    ) -> None:
        self._connect_factory = connect_factory
        self._uuid_factory = uuid_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_current_case(
        self,
        *,
        org_id: str,
        project_id: str,
        request: CreateIntegrationCaseRequest,
        owner: str,
        required_markings: Sequence[str],
    ) -> StoredIntegrationCase:
        try:
            with self._connect_factory() as conn:
                result = self.create_current_case_in_transaction(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    request=request,
                    owner=owner,
                    required_markings=required_markings,
                )
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                conn.commit()
                return result
        except (AssetNotFoundError, EvidenceReferenceInvalidError):
            raise
        except errors.UniqueViolation as exc:
            raise RevisionConflictError(
                "integration case identity already exists"
            ) from exc
        except (errors.CheckViolation, errors.ForeignKeyViolation) as exc:
            raise EvidenceReferenceInvalidError(
                "integration case binding violates canonical persistence constraints"
            ) from exc
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def create_current_case_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        request: CreateIntegrationCaseRequest,
        owner: str,
        required_markings: Sequence[str],
    ) -> StoredIntegrationCase:
        org_id = _text(org_id, "org_id")
        project_id = _text(project_id, "project_id")
        owner = _text(owner, "owner")
        markings = _markings(required_markings)
        request = CreateIntegrationCaseRequest.model_validate(request)
        binding = conn.execute(
            """
            SELECT i.installation_pk, i.installation_id, i.active_revision,
                   r.composition_pk, c.composition_id, r.lock_revision,
                   r.lock_hash, r.overlay_revision
              FROM bundle_installation AS i
              JOIN bundle_installation_revision AS r
                ON r.org_id = i.org_id AND r.project_id = i.project_id
               AND r.installation_pk = i.installation_pk
               AND r.revision = i.active_revision
              JOIN bundle_composition AS c
                ON c.org_id = r.org_id AND c.project_id = r.project_id
               AND c.composition_pk = r.composition_pk
             WHERE i.org_id = %s AND i.project_id = %s
               AND i.installation_id = %s AND r.state = 'active'
            """,
            (org_id, project_id, uuid.UUID(request.installation_id)),
        ).fetchone()
        if binding is None or binding["overlay_revision"] != request.overlay_revision:
            raise AssetNotFoundError("active installation binding not found")
        now = _utc(self._clock())
        case_pk, case_id, instance_pk = (
            self._uuid_factory(),
            self._uuid_factory(),
            self._uuid_factory(),
        )
        conn.execute(
            """
            INSERT INTO integration_case (
              org_id, project_id, case_pk, case_id, scope, display_name,
              owner, required_markings, created_at, updated_at
            ) VALUES (%s,%s,%s,%s,'current',%s,%s,%s,%s,%s)
            """,
            (
                org_id,
                project_id,
                case_pk,
                case_id,
                request.display_name,
                owner,
                Jsonb(markings),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO integration_instance (
              org_id, project_id, instance_pk, case_pk, current_revision,
              etag_version, created_at, updated_at
            ) VALUES (%s,%s,%s,%s,1,1,%s,%s)
            """,
            (org_id, project_id, instance_pk, case_pk, now, now),
        )
        conn.execute(
            """
            INSERT INTO integration_instance_revision (
              org_id, project_id, instance_pk, revision, parent_revision,
              installation_pk, installation_revision, composition_pk,
              lock_revision, lock_hash, overlay_revision, required_markings,
              created_at
            ) VALUES (%s,%s,%s,1,NULL,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                org_id,
                project_id,
                instance_pk,
                binding["installation_pk"],
                binding["active_revision"],
                binding["composition_pk"],
                binding["lock_revision"],
                binding["lock_hash"],
                binding["overlay_revision"],
                Jsonb(markings),
                now,
            ),
        )
        self._insert_projection(
            conn,
            org_id=org_id,
            project_id=project_id,
            case_pk=case_pk,
            case_id=str(case_id),
            instance_pk=instance_pk,
            instance_revision=1,
            etag_version=1,
            snapshot_revision=1,
            cutoff_at=now,
            evidence=(),
            old_stage=None,
            cause="created",
            scope="current",
            updated_at=now,
        )
        return _load_case_by_pk(conn, org_id, project_id, case_pk)

    def create_reference_case(
        self,
        *,
        org_id: str,
        project_id: str,
        display_name: str,
        required_markings: Sequence[str] = (),
    ) -> StoredIntegrationCase:
        """Create one already-redacted, immutable reference copy."""
        org_id, project_id = _text(org_id, "org_id"), _text(project_id, "project_id")
        display_name, markings = (
            _text(display_name, "display_name"),
            _markings(required_markings),
        )
        now = _utc(self._clock())
        case_pk, case_id, instance_pk = (
            self._uuid_factory(),
            self._uuid_factory(),
            self._uuid_factory(),
        )
        try:
            with self._connect_factory() as conn:
                conn.execute(
                    """INSERT INTO integration_case (
                         org_id,project_id,case_pk,case_id,scope,display_name,
                         owner,required_markings,created_at,updated_at
                       ) VALUES (%s,%s,%s,%s,'reference',%s,NULL,%s,%s,%s)""",
                    (
                        org_id,
                        project_id,
                        case_pk,
                        case_id,
                        display_name,
                        Jsonb(markings),
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """INSERT INTO integration_instance (
                         org_id,project_id,instance_pk,case_pk,current_revision,
                         etag_version,created_at,updated_at
                       ) VALUES (%s,%s,%s,%s,1,1,%s,%s)""",
                    (org_id, project_id, instance_pk, case_pk, now, now),
                )
                conn.execute(
                    """INSERT INTO integration_instance_revision (
                         org_id,project_id,instance_pk,revision,parent_revision,
                         installation_pk,installation_revision,composition_pk,
                         lock_revision,lock_hash,overlay_revision,required_markings,
                         created_at
                       ) VALUES (%s,%s,%s,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,%s,%s)""",
                    (org_id, project_id, instance_pk, Jsonb(markings), now),
                )
                self._insert_projection(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    case_pk=case_pk,
                    case_id=str(case_id),
                    instance_pk=instance_pk,
                    instance_revision=1,
                    etag_version=1,
                    snapshot_revision=1,
                    cutoff_at=now,
                    evidence=(),
                    old_stage=None,
                    cause="created",
                    scope="reference",
                    updated_at=now,
                )
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                conn.commit()
                return _load_case_by_pk(conn, org_id, project_id, case_pk)
        except (errors.CheckViolation, errors.ForeignKeyViolation) as exc:
            raise EvidenceReferenceInvalidError(
                "reference case violates canonical persistence constraints"
            ) from exc
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def append_evidence(
        self,
        *,
        org_id: str,
        project_id: str,
        case_id: str,
        evidence: IntegrationEvidenceEnvelope,
    ) -> IntegrationEvidenceEnvelope:
        try:
            with self._connect_factory() as conn:
                case = _lock_case(conn, org_id, project_id, case_id)
                result = self.append_evidence_in_transaction(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    case_pk=case["case_pk"],
                    evidence=evidence,
                )
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                conn.commit()
                return result
        except (AssetNotFoundError, EvidenceReferenceInvalidError):
            raise
        except (
            errors.CheckViolation,
            errors.ForeignKeyViolation,
            errors.UniqueViolation,
        ) as exc:
            raise EvidenceReferenceInvalidError(
                "evidence revision violates canonical persistence constraints"
            ) from exc
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def append_evidence_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        case_pk: uuid.UUID,
        evidence: IntegrationEvidenceEnvelope,
    ) -> IntegrationEvidenceEnvelope:
        item = INTEGRATION_EVIDENCE_ADAPTER.validate_python(evidence)
        envelope = item.model_dump(mode="json", by_alias=True, exclude_none=False)
        expected_hash = canonical_sha256(
            {key: value for key, value in envelope.items() if key != "evidenceHash"}
        )
        if item.evidence_hash != expected_hash:
            raise EvidenceReferenceInvalidError("evidenceHash is not canonical")
        previous = conn.execute(
            """
            SELECT evidence_pk, evidence_id, revision
              FROM integration_evidence
             WHERE org_id=%s AND project_id=%s AND case_pk=%s
               AND producer=%s AND series_key=%s
             ORDER BY revision DESC LIMIT 1
            """,
            (org_id, project_id, case_pk, item.producer, item.series_key),
        ).fetchone()
        if previous is None:
            if item.revision != 1:
                raise EvidenceReferenceInvalidError("first evidence revision must be 1")
            evidence_pk = self._uuid_factory()
        else:
            if (
                item.revision != previous["revision"] + 1
                or uuid.UUID(item.evidence_id) != previous["evidence_id"]
            ):
                raise EvidenceReferenceInvalidError(
                    "evidence revision is not the series tail"
                )
            evidence_pk = previous["evidence_pk"]
        conn.execute(
            """
            INSERT INTO integration_evidence (
              org_id, project_id, evidence_pk, evidence_id, case_pk, revision,
              evidence_type, series_key, subject_ref, artifact_ref,
              artifact_hash, outcome, observed_at, expires_at, revoked_at,
              required_markings, producer, claims_json, envelope_json,
              evidence_hash, recorded_at
            ) VALUES (
              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            """,
            (
                org_id,
                project_id,
                evidence_pk,
                uuid.UUID(item.evidence_id),
                case_pk,
                item.revision,
                item.evidence_type.value,
                item.series_key,
                item.subject_ref,
                item.artifact_ref,
                item.artifact_hash,
                item.outcome.value,
                item.observed_at,
                item.expires_at,
                item.revoked_at,
                Jsonb(item.required_markings),
                item.producer,
                Jsonb(envelope["claims"]),
                Jsonb(envelope),
                item.evidence_hash,
                item.recorded_at,
            ),
        )
        return deepcopy(item)

    def project_case(
        self,
        *,
        org_id: str,
        project_id: str,
        case_id: str,
        if_match_etag: int,
        evidence: Sequence[IntegrationEvidenceEnvelope] = (),
        cause: str = "projection_rebuilt",
    ) -> ProjectionSnapshot:
        try:
            with self._connect_factory() as conn:
                case = _lock_case(conn, org_id, project_id, case_id)
                result = self.project_case_in_transaction(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    case=case,
                    if_match_etag=if_match_etag,
                    evidence=evidence,
                    cause=cause,
                )
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                conn.commit()
                return result
        except (
            AssetNotFoundError,
            RevisionConflictError,
            EvidenceReferenceInvalidError,
            EvidenceIntegrityCorruptError,
        ):
            raise
        except (
            errors.CheckViolation,
            errors.ForeignKeyViolation,
            errors.UniqueViolation,
        ) as exc:
            raise EvidenceReferenceInvalidError(
                "projection violates canonical persistence constraints"
            ) from exc
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def project_case_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        case: Any,
        if_match_etag: int,
        evidence: Sequence[IntegrationEvidenceEnvelope] = (),
        cause: str = "projection_rebuilt",
    ) -> ProjectionSnapshot:
        if case["scope"] != "current":
            raise AssetNotFoundError("integration case not found")
        if case["etag_version"] != if_match_etag:
            raise RevisionConflictError("integration case ETag is stale")
        now = _utc(self._clock())
        new_revision = case["current_revision"] + 1
        conn.execute(
            """
            INSERT INTO integration_instance_revision (
              org_id,project_id,instance_pk,revision,parent_revision,
              installation_pk,installation_revision,composition_pk,lock_revision,
              lock_hash,overlay_revision,required_markings,created_at
            )
            SELECT org_id,project_id,instance_pk,%s,%s,
                   installation_pk,installation_revision,composition_pk,lock_revision,
                   lock_hash,overlay_revision,required_markings,%s
              FROM integration_instance_revision
             WHERE org_id=%s AND project_id=%s AND instance_pk=%s
               AND revision=%s
            """,
            (
                new_revision,
                case["current_revision"],
                now,
                org_id,
                project_id,
                case["instance_pk"],
                case["current_revision"],
            ),
        )
        conn.execute(
            """
            UPDATE integration_instance
               SET current_revision=%s, etag_version=%s, updated_at=%s
             WHERE org_id=%s AND project_id=%s AND instance_pk=%s
            """,
            (
                new_revision,
                if_match_etag + 1,
                now,
                org_id,
                project_id,
                case["instance_pk"],
            ),
        )
        for item in evidence:
            self.append_evidence_in_transaction(
                conn,
                org_id=org_id,
                project_id=project_id,
                case_pk=case["case_pk"],
                evidence=item,
            )
        heads = _load_evidence_heads(conn, org_id, project_id, case["case_pk"], now)
        previous = conn.execute(
            """SELECT snapshot_revision, computed_stage FROM integration_case_projection
                 WHERE org_id=%s AND project_id=%s AND case_pk=%s""",
            (org_id, project_id, case["case_pk"]),
        ).fetchone()
        return self._insert_projection(
            conn,
            org_id=org_id,
            project_id=project_id,
            case_pk=case["case_pk"],
            case_id=str(case["case_id"]),
            instance_pk=case["instance_pk"],
            instance_revision=new_revision,
            etag_version=if_match_etag + 1,
            snapshot_revision=previous["snapshot_revision"] + 1,
            cutoff_at=now,
            evidence=heads,
            old_stage=IntegrationStage(previous["computed_stage"]),
            cause=cause,
            scope="current",
            updated_at=now,
        )

    def _insert_projection(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        case_pk: uuid.UUID,
        case_id: str,
        instance_pk: uuid.UUID,
        instance_revision: int,
        etag_version: int,
        snapshot_revision: int,
        cutoff_at: datetime,
        evidence: Sequence[IntegrationEvidenceEnvelope],
        old_stage: IntegrationStage | None,
        cause: str,
        scope: Literal["current", "reference"],
        updated_at: datetime,
    ) -> ProjectionSnapshot:
        policy = evaluate_contract_stage_policy(
            planned_basis=PlannedBasis(
                exact_instance_revision=True,
                active_installation_revision=scope == "current",
                composition_lock_valid=scope == "current",
                composition_hash_valid=scope == "current",
            ),
            evidence=list(evidence),
            cutoff_at=cutoff_at,
        )
        stage = IntegrationStage(policy.stage.value if policy.stage else "planned")
        gates, blockers, blocker_refs = _policy_documents(
            case_id, policy, cutoff_at, stage
        )
        evidence_json = [
            item.model_dump(mode="json", by_alias=True, exclude_none=False)
            for item in evidence
        ]
        snapshot = {
            "caseId": case_id,
            "snapshotRevision": snapshot_revision,
            "instanceRevision": instance_revision,
            "cutoffAt": cutoff_at.isoformat().replace("+00:00", "Z"),
            "nextProjectionAt": (
                policy.next_projection_at.isoformat().replace("+00:00", "Z")
                if policy.next_projection_at
                else None
            ),
            "evidence": evidence_json,
            "computedStage": stage.value,
            "stagePolicyVersion": STAGE_POLICY_VERSION,
            "stageGates": gates,
            "blockerRefs": blocker_refs,
        }
        snapshot_hash = canonical_sha256(snapshot)
        snapshot["snapshotHash"] = snapshot_hash
        conn.execute(
            """
            INSERT INTO integration_evidence_snapshot (
              org_id,project_id,case_pk,snapshot_revision,instance_pk,
              instance_revision,snapshot_json,snapshot_hash,cutoff_at,
              next_projection_at,computed_stage,stage_policy_version,
              evidence_count,stage_gates_json,blocker_refs_json,etag_version,
              created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                org_id,
                project_id,
                case_pk,
                snapshot_revision,
                instance_pk,
                instance_revision,
                Jsonb(snapshot),
                snapshot_hash,
                cutoff_at,
                policy.next_projection_at,
                stage.value,
                STAGE_POLICY_VERSION,
                len(evidence),
                Jsonb(gates),
                Jsonb(blocker_refs),
                etag_version,
                updated_at,
            ),
        )
        event: IntegrationStageEvent | None = None
        if old_stage is None or old_stage != stage:
            sequence = conn.execute(
                """SELECT COALESCE(MAX(sequence),0)+1 AS sequence
                     FROM integration_stage_event
                    WHERE org_id=%s AND project_id=%s AND case_pk=%s""",
                (org_id, project_id, case_pk),
            ).fetchone()["sequence"]
            event_json = {
                "sequence": sequence,
                "snapshotRevision": snapshot_revision,
                "oldStage": old_stage.value if old_stage else None,
                "newStage": stage.value,
                "cause": cause,
                "reasonRefs": blocker_refs,
                "createdAt": updated_at,
            }
            event = IntegrationStageEvent.model_validate(event_json)
            conn.execute(
                """
                INSERT INTO integration_stage_event (
                  org_id,project_id,case_pk,sequence,snapshot_revision,
                  old_stage,new_stage,cause,reason_refs,created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    org_id,
                    project_id,
                    case_pk,
                    sequence,
                    snapshot_revision,
                    old_stage.value if old_stage else None,
                    stage.value,
                    cause,
                    Jsonb(blocker_refs),
                    updated_at,
                ),
            )
        metrics = (
            _projection_metrics(evidence, cutoff_at)
            if scope == "current"
            else ProjectionMetrics(None, None, None, None)
        )
        conn.execute(
            """
            INSERT INTO integration_case_projection (
              org_id,project_id,case_pk,instance_pk,instance_revision,
              snapshot_revision,computed_stage,stage_policy_version,cutoff_at,
              next_projection_at,stage_gates_json,blockers_json,connector_count,
              pipeline_count,dataset_row_count,latency_ms,blocker_count,
              etag_version,updated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id,project_id,case_pk) DO UPDATE SET
              instance_revision=EXCLUDED.instance_revision,
              snapshot_revision=EXCLUDED.snapshot_revision,
              computed_stage=EXCLUDED.computed_stage,
              stage_policy_version=EXCLUDED.stage_policy_version,
              cutoff_at=EXCLUDED.cutoff_at,
              next_projection_at=EXCLUDED.next_projection_at,
              stage_gates_json=EXCLUDED.stage_gates_json,
              blockers_json=EXCLUDED.blockers_json,
              connector_count=EXCLUDED.connector_count,
              pipeline_count=EXCLUDED.pipeline_count,
              dataset_row_count=EXCLUDED.dataset_row_count,
              latency_ms=EXCLUDED.latency_ms,
              blocker_count=EXCLUDED.blocker_count,
              etag_version=EXCLUDED.etag_version,
              updated_at=EXCLUDED.updated_at
            """,
            (
                org_id,
                project_id,
                case_pk,
                instance_pk,
                instance_revision,
                snapshot_revision,
                stage.value,
                STAGE_POLICY_VERSION,
                cutoff_at,
                policy.next_projection_at,
                Jsonb(gates),
                Jsonb(blockers),
                metrics.connector_count,
                metrics.pipeline_count,
                metrics.dataset_row_count,
                metrics.latency_ms,
                sum(item["status"] == "open" for item in blockers),
                etag_version,
                updated_at,
            ),
        )
        response = IntegrationEvidenceSnapshotResponse.model_validate(
            {
                "caseId": case_id,
                "snapshotRevision": snapshot_revision,
                "instanceRevision": instance_revision,
                "cutoffAt": cutoff_at,
                "computedStage": stage.value,
                "stagePolicyVersion": STAGE_POLICY_VERSION,
                "snapshotHash": snapshot_hash,
                "nextProjectionAt": policy.next_projection_at,
                "evidenceCount": len(evidence),
                "stageGates": gates,
                "blockerRefs": blocker_refs,
                "etagVersion": etag_version,
                "createdAt": updated_at,
            }
        )
        return ProjectionSnapshot(response=response, stage_event=event, metrics=metrics)

    def execute_idempotent(
        self,
        *,
        org_id: str,
        project_id: str,
        operation: Literal["integration_cases.create", "integration_cases.project"],
        idempotency_key: str,
        subject: str,
        request_json: JsonObject,
        if_match_etag: int | None,
        handler: CommandHandler,
    ) -> IntegrationCommandReceipt:
        org_id, project_id = _text(org_id, "org_id"), _text(project_id, "project_id")
        idempotency_key, subject = (
            _text(idempotency_key, "idempotency_key"),
            _text(subject, "subject"),
        )
        request_hash = canonical_sha256(
            {"body": request_json, "ifMatch": if_match_etag}
        )
        try:
            with self._connect_factory() as conn:
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"{org_id}\x1f{project_id}\x1f{operation}\x1f{idempotency_key}",),
                )
                row = conn.execute(
                    """SELECT case_pk,subject,request_hash,if_match_etag,status_code,
                              response_json,response_etag
                         FROM integration_case_command
                        WHERE org_id=%s AND project_id=%s AND operation=%s
                          AND idempotency_key=%s""",
                    (org_id, project_id, operation, idempotency_key),
                ).fetchone()
                if row is not None:
                    if (
                        row["subject"] != subject
                        or row["request_hash"] != request_hash
                        or row["if_match_etag"] != if_match_etag
                    ):
                        raise IdempotencyConflictError("idempotency key was reused")
                    return IntegrationCommandReceipt(
                        case_pk=row["case_pk"],
                        status_code=row["status_code"],
                        response_json=deepcopy(row["response_json"]),
                        response_etag=row["response_etag"],
                        replayed=True,
                    )
                result = handler(conn)
                _validate_command_result(result)
                conn.execute(
                    """INSERT INTO integration_case_command (
                         org_id,project_id,operation,idempotency_key,case_pk,subject,
                         request_hash,if_match_etag,status_code,response_json,
                         response_etag
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        org_id,
                        project_id,
                        operation,
                        idempotency_key,
                        result.case_pk,
                        subject,
                        request_hash,
                        if_match_etag,
                        result.status_code,
                        Jsonb(result.response_json),
                        result.response_etag,
                    ),
                )
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                conn.commit()
                return IntegrationCommandReceipt(
                    case_pk=result.case_pk,
                    status_code=result.status_code,
                    response_json=deepcopy(result.response_json),
                    response_etag=result.response_etag,
                    replayed=False,
                )
        except (
            IdempotencyConflictError,
            AssetNotFoundError,
            RevisionConflictError,
            EvidenceReferenceInvalidError,
            EvidenceIntegrityCorruptError,
        ):
            raise
        except (
            errors.CheckViolation,
            errors.ForeignKeyViolation,
            errors.UniqueViolation,
        ) as exc:
            raise EvidenceReferenceInvalidError(
                "command receipt is inconsistent"
            ) from exc
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def get_case(
        self, *, org_id: str, project_id: str, case_id: str
    ) -> StoredIntegrationCase:
        try:
            with self._connect_factory() as conn:
                case = _load_case_by_public_id(conn, org_id, project_id, case_id)
                _verify_case_integrity(conn, case)
                return case
        except (AssetNotFoundError, EvidenceIntegrityCorruptError):
            raise
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def reference_counts(self, *, org_id: str, project_id: str) -> tuple[int, int]:
        """Return current/reference counts separately; reference never contaminates current."""
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """SELECT COUNT(*) FILTER (WHERE scope='current') AS current_count,
                              COUNT(*) FILTER (WHERE scope='reference') AS reference_count
                         FROM integration_case WHERE org_id=%s AND project_id=%s""",
                    (_text(org_id, "org_id"), _text(project_id, "project_id")),
                ).fetchone()
                return row["current_count"], row["reference_count"]
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc


def _lock_case(conn: Any, org_id: str, project_id: str, case_id: str) -> Any:
    org_id, project_id = _text(org_id, "org_id"), _text(project_id, "project_id")
    try:
        case_uuid = uuid.UUID(case_id)
    except (TypeError, ValueError) as exc:
        raise AssetNotFoundError("integration case not found") from exc
    row = conn.execute(
        """SELECT c.*,i.instance_pk,i.current_revision,i.etag_version
             FROM integration_case c JOIN integration_instance i
               ON i.org_id=c.org_id AND i.project_id=c.project_id
              AND i.case_pk=c.case_pk
            WHERE c.org_id=%s AND c.project_id=%s AND c.case_id=%s
            FOR UPDATE OF c,i""",
        (org_id, project_id, case_uuid),
    ).fetchone()
    if row is None:
        raise AssetNotFoundError("integration case not found")
    return row


def _load_evidence_heads(
    conn: Any, org_id: str, project_id: str, case_pk: uuid.UUID, cutoff: datetime
) -> list[IntegrationEvidenceEnvelope]:
    rows = conn.execute(
        """SELECT DISTINCT ON (producer,series_key) envelope_json,evidence_hash
             FROM integration_evidence
            WHERE org_id=%s AND project_id=%s AND case_pk=%s AND recorded_at<=%s
            ORDER BY producer,series_key,revision DESC""",
        (org_id, project_id, case_pk, cutoff),
    ).fetchall()
    result: list[IntegrationEvidenceEnvelope] = []
    for row in rows:
        try:
            item = INTEGRATION_EVIDENCE_ADAPTER.validate_json(
                json.dumps(row["envelope_json"], separators=(",", ":"))
            )
        except ValidationError as exc:
            raise EvidenceIntegrityCorruptError() from exc
        payload = item.model_dump(mode="json", by_alias=True, exclude_none=False)
        if item.evidence_hash != row[
            "evidence_hash"
        ] or item.evidence_hash != canonical_sha256(
            {k: v for k, v in payload.items() if k != "evidenceHash"}
        ):
            raise EvidenceIntegrityCorruptError()
        result.append(item)
    return result


def _load_case_by_public_id(
    conn: Any, org_id: str, project_id: str, case_id: str
) -> StoredIntegrationCase:
    row = _lock_case(conn, org_id, project_id, case_id)
    return _load_case_by_pk(conn, row["org_id"], row["project_id"], row["case_pk"])


def _load_case_by_pk(
    conn: Any, org_id: str, project_id: str, case_pk: uuid.UUID
) -> StoredIntegrationCase:
    row = conn.execute(
        """
        SELECT c.*,i.instance_pk,i.current_revision,i.etag_version,
               r.installation_pk,bi.installation_id,r.installation_revision,
               r.composition_pk,bc.composition_id,r.lock_revision,r.lock_hash,
               r.overlay_revision,p.snapshot_revision,p.computed_stage
          FROM integration_case c
          JOIN integration_instance i ON i.org_id=c.org_id AND i.project_id=c.project_id AND i.case_pk=c.case_pk
          JOIN integration_instance_revision r ON r.org_id=i.org_id AND r.project_id=i.project_id AND r.instance_pk=i.instance_pk AND r.revision=i.current_revision
          JOIN integration_case_projection p ON p.org_id=c.org_id AND p.project_id=c.project_id AND p.case_pk=c.case_pk
          LEFT JOIN bundle_installation bi ON bi.org_id=r.org_id AND bi.project_id=r.project_id AND bi.installation_pk=r.installation_pk
          LEFT JOIN bundle_composition bc ON bc.org_id=r.org_id AND bc.project_id=r.project_id AND bc.composition_pk=r.composition_pk
         WHERE c.org_id=%s AND c.project_id=%s AND c.case_pk=%s
        """,
        (org_id, project_id, case_pk),
    ).fetchone()
    if row is None:
        raise AssetNotFoundError("integration case not found")
    return StoredIntegrationCase(
        org_id=row["org_id"],
        project_id=row["project_id"],
        case_pk=row["case_pk"],
        case_id=str(row["case_id"]),
        instance_pk=row["instance_pk"],
        scope=row["scope"],
        display_name=row["display_name"],
        owner=row["owner"],
        required_markings=tuple(row["required_markings"]),
        current_revision=row["current_revision"],
        etag_version=row["etag_version"],
        installation_pk=row["installation_pk"],
        installation_id=str(row["installation_id"]) if row["installation_id"] else None,
        installation_revision=row["installation_revision"],
        composition_pk=row["composition_pk"],
        composition_id=str(row["composition_id"]) if row["composition_id"] else None,
        lock_revision=row["lock_revision"],
        lock_hash=row["lock_hash"],
        overlay_revision=row["overlay_revision"],
        snapshot_revision=row["snapshot_revision"],
        computed_stage=IntegrationStage(row["computed_stage"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _verify_case_integrity(conn: Any, case: StoredIntegrationCase) -> None:
    rows = conn.execute(
        """SELECT snapshot_revision,snapshot_json,snapshot_hash,computed_stage
             FROM integration_evidence_snapshot
            WHERE org_id=%s AND project_id=%s AND case_pk=%s
            ORDER BY snapshot_revision""",
        (case.org_id, case.project_id, case.case_pk),
    ).fetchall()
    if [r["snapshot_revision"] for r in rows] != list(
        range(1, case.snapshot_revision + 1)
    ):
        raise EvidenceIntegrityCorruptError()
    for row in rows:
        payload = dict(row["snapshot_json"])
        actual = payload.pop("snapshotHash", None)
        if actual != row["snapshot_hash"] or actual != canonical_sha256(payload):
            raise EvidenceIntegrityCorruptError()
        if payload.get("computedStage") != row["computed_stage"]:
            raise EvidenceIntegrityCorruptError()
    events = conn.execute(
        """SELECT sequence,old_stage,new_stage,snapshot_revision
             FROM integration_stage_event
            WHERE org_id=%s AND project_id=%s AND case_pk=%s ORDER BY sequence""",
        (case.org_id, case.project_id, case.case_pk),
    ).fetchall()
    if not events or [r["sequence"] for r in events] != list(range(1, len(events) + 1)):
        raise EvidenceIntegrityCorruptError()
    previous = None
    for row in events:
        if row["old_stage"] != previous or row["new_stage"] == previous:
            raise EvidenceIntegrityCorruptError()
        previous = row["new_stage"]
    if (
        previous != case.computed_stage.value
        or events[-1]["snapshot_revision"] > case.snapshot_revision
    ):
        raise EvidenceIntegrityCorruptError()
    _load_evidence_heads(
        conn,
        case.org_id,
        case.project_id,
        case.case_pk,
        datetime.max.replace(tzinfo=UTC),
    )


def _policy_documents(
    case_id: str,
    policy: StagePolicyResult,
    cutoff: datetime,
    computed_stage: IntegrationStage,
) -> tuple[list[JsonObject], list[JsonObject], list[str]]:
    gates: list[JsonObject] = []
    blockers: list[JsonObject] = []
    refs: list[str] = []
    computed_rank = list(IntegrationStage).index(computed_stage)
    for gate_index, gate in enumerate(policy.gates):
        gate_refs: list[str] = []
        for blocker in gate.blockers:
            token = ":".join(
                part
                for part in (
                    gate.stage.value,
                    blocker.code.value,
                    blocker.evidence_type.value if blocker.evidence_type else None,
                    blocker.series_key,
                )
                if part
            )
            blocker_id = str(uuid.uuid5(uuid.UUID(case_id), token))
            gate_refs.append(blocker_id)
            refs.append(blocker_id)
            blockers.append(
                {
                    "blockerId": blocker_id,
                    "code": blocker.code.value,
                    "severity": "high",
                    "status": "open",
                    "gate": gate.stage.value,
                    "reasonRefs": [token],
                    "evidenceRefs": [blocker.evidence_ref]
                    if blocker.evidence_ref
                    else [],
                    "owner": None,
                    "firstObservedAt": cutoff.isoformat().replace("+00:00", "Z"),
                    "updatedAt": cutoff.isoformat().replace("+00:00", "Z"),
                }
            )
        status = (
            "satisfied"
            if gate_index <= computed_rank
            else ("blocked" if gate_index == computed_rank + 1 else "not_evaluated")
        )
        gates.append(
            {
                "stage": gate.stage.value,
                "status": status,
                "evidenceRefs": sorted(gate.evidence_refs),
                "reasonRefs": sorted(gate_refs),
            }
        )
    return gates, blockers, sorted(set(refs))


def _projection_metrics(
    evidence: Sequence[IntegrationEvidenceEnvelope], cutoff: datetime
) -> ProjectionMetrics:
    valid = [
        item
        for item in evidence
        if item.outcome.value == "valid"
        and item.observed_at <= cutoff
        and item.revoked_at is None
        and (item.expires_at is None or cutoff < item.expires_at)
    ]
    connectors = {
        item.subject_ref
        for item in valid
        if item.evidence_type.value == "source_connection"
        and item.claims.read_probe
        and item.claims.tenant_binding
    }
    pipelines = {
        item.subject_ref
        for item in valid
        if item.evidence_type.value == "pipeline_run"
        and item.claims.result == "succeeded"
    }
    datasets: dict[tuple[str, str], int | None] = {}
    latencies: list[int] = []
    for item in valid:
        if item.evidence_type.value == "dataset_revision":
            datasets[(item.subject_ref, item.claims.revision)] = item.claims.row_count
        elif (
            item.evidence_type.value == "runtime_health"
            and item.claims.healthy
            and item.claims.latency_ms is not None
        ):
            latencies.append(item.claims.latency_ms)
    measured_rows = [value for value in datasets.values() if value is not None]
    return ProjectionMetrics(
        len(connectors) if connectors else None,
        len(pipelines) if pipelines else None,
        sum(measured_rows) if measured_rows else None,
        max(latencies) if latencies else None,
    )


def _validate_command_result(result: IntegrationCommandResult) -> None:
    if not 200 <= result.status_code <= 299 or not _STRONG_ETAG.fullmatch(
        result.response_etag
    ):
        raise EvidenceReferenceInvalidError("command result is not canonical")


def _text(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"{label} must be normalized text")
    return value


def _markings(values: Iterable[str]) -> list[str]:
    result = sorted({_text(value, "required marking") for value in values})
    if len(result) > 64:
        raise ValueError("too many required markings")
    return result


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return an aware datetime")
    return value.astimezone(UTC)
