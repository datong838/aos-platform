"""Tenant-scoped PostgreSQL store for governed AIP memory facts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_contracts import (
    GovernanceApprovalRef,
    KnowledgeScope,
    KnowledgeSourceRef,
    MemoryCandidate,
    MemoryCandidateEvent,
    MemoryCandidateStatus,
    MemoryItem,
    MemoryItemRevision,
    MemoryItemStatus,
    SubmitMemoryCandidateRequest,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipMemoryStoreError(RuntimeError):
    code = "AIP_MEMORY_STORE_ERROR"


class AipMemoryNotFound(AipMemoryStoreError):
    code = "AIP_MEMORY_NOT_FOUND"


class AipMemoryConflict(AipMemoryStoreError):
    code = "AIP_MEMORY_CONFLICT"


class AipMemoryTransitionBlocked(AipMemoryStoreError):
    code = "AIP_MEMORY_TRANSITION_BLOCKED"


class AipMemoryPersistenceError(AipMemoryStoreError):
    code = "AIP_MEMORY_PERSISTENCE_ERROR"


_ALLOWED: dict[MemoryCandidateStatus, frozenset[MemoryCandidateStatus]] = {
    MemoryCandidateStatus.PENDING: frozenset(
        {
            MemoryCandidateStatus.QUARANTINED,
            MemoryCandidateStatus.REJECTED,
            MemoryCandidateStatus.APPROVED,
        }
    ),
    MemoryCandidateStatus.QUARANTINED: frozenset(
        {
            MemoryCandidateStatus.PENDING,
            MemoryCandidateStatus.REJECTED,
            MemoryCandidateStatus.APPROVED,
        }
    ),
    MemoryCandidateStatus.APPROVED: frozenset({MemoryCandidateStatus.PROMOTED}),
}


class AipMemoryStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create_source_revision(
        self,
        scope: TenantScope,
        source_id: str,
        revision: int,
        source: KnowledgeSourceRef,
        *,
        actor: str,
    ) -> KnowledgeSourceRef:
        self._require_scope(scope)
        if revision < 1 or not source_id.strip() or not actor.strip():
            raise ValueError("source id, revision and actor are required")
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    """INSERT INTO aip_memory_source_revision (
                       org_id,project_id,source_id,revision,source_kind,source_uri,
                       source_ref,observed_at,freshness_expires_at,license_id,
                       usage_policy,content_hash,provider,provider_version,
                       applicability,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,
                         %s::jsonb,%s)
                       ON CONFLICT (org_id,project_id,source_id,revision) DO NOTHING
                       RETURNING *""",
                    (
                        *scope.key,
                        source_id.strip(),
                        revision,
                        source.source_kind.value,
                        source.source_uri,
                        self._json_nullable(source.source_ref),
                        source.observed_at,
                        source.freshness_expires_at,
                        source.license_id,
                        source.usage_policy,
                        source.content_hash,
                        source.provider,
                        source.provider_version,
                        self._json(source.applicability),
                        actor.strip(),
                    ),
                ).fetchone()
                if row is None:
                    row = self._source_row(conn, scope, source_id, revision)
                    if row is None or self._source_from_row(row) != source:
                        raise AipMemoryConflict("source revision already has different content")
                conn.commit()
                return self._source_from_row(row)
        except AipMemoryStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPersistenceError("source revision persistence failed") from exc

    def submit_candidate(
        self,
        scope: TenantScope,
        candidate_id: str,
        request: SubmitMemoryCandidateRequest,
        *,
        source_id: str,
        source_revision: int,
        knowledge_scope: KnowledgeScope,
        actor: str,
        occurred_at: datetime,
    ) -> MemoryCandidate:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                source_row = self._source_row(conn, scope, source_id, source_revision)
                if source_row is None or self._source_from_row(source_row) != request.source:
                    raise AipMemoryConflict("candidate source revision drifted")
                self._require_task_run(conn, scope, request.task_id, request.run_id)
                existing = self._candidate_row(conn, scope, candidate_id)
                if existing is not None:
                    candidate = self._candidate_from_row(conn, scope, existing)
                    if (
                        candidate.request != request
                        or candidate.scope is not knowledge_scope
                    ):
                        raise AipMemoryConflict("candidate id was reused with different content")
                    return candidate
                event = self._candidate_event(
                    scope,
                    candidate_id,
                    sequence=1,
                    from_status=None,
                    to_status=MemoryCandidateStatus.PENDING,
                    reasons=[],
                    evidence_ref=None,
                    actor=actor,
                    occurred_at=occurred_at,
                )
                inserted = conn.execute(
                    """INSERT INTO aip_memory_candidate (
                       org_id,project_id,candidate_id,memory_layer,scope,status,
                       task_id,run_id,subject_ref,payload_ref,source_id,source_revision,
                       confidence,markings,created_by,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,'pending',%s,%s,%s::jsonb,%s::jsonb,
                         %s,%s,%s,%s::jsonb,%s,%s,%s)
                       ON CONFLICT (org_id,project_id,candidate_id) DO NOTHING
                       RETURNING candidate_id""",
                    (
                        *scope.key,
                        candidate_id,
                        request.candidate_layer.value,
                        knowledge_scope.value,
                        request.task_id,
                        request.run_id,
                        self._json(request.subject),
                        self._json(request.payload),
                        source_id,
                        source_revision,
                        request.confidence,
                        self._json(request.marking),
                        actor,
                        occurred_at,
                        occurred_at,
                    ),
                ).fetchone()
                if inserted is None:
                    replay = self._candidate_row(conn, scope, candidate_id)
                    if replay is None:
                        raise AipMemoryConflict("candidate concurrent insert disappeared")
                    candidate = self._candidate_from_row(conn, scope, replay)
                    if candidate.request != request or candidate.scope is not knowledge_scope:
                        raise AipMemoryConflict(
                            "candidate id was reused with different content"
                        )
                    return candidate
                self._insert_event(conn, scope, event)
                conn.commit()
                row = self._candidate_row(conn, scope, candidate_id)
                return self._candidate_from_row(conn, scope, row)
        except AipMemoryStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPersistenceError("candidate persistence failed") from exc

    def get_candidate(self, scope: TenantScope, candidate_id: str) -> MemoryCandidate:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._candidate_row(conn, scope, candidate_id)
                if row is None:
                    raise AipMemoryNotFound("candidate not found")
                return self._candidate_from_row(conn, scope, row)
        except AipMemoryStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPersistenceError("candidate read failed") from exc

    def list_candidates(
        self,
        scope: TenantScope,
        *,
        status: MemoryCandidateStatus | None = None,
        limit: int = 100,
    ) -> list[MemoryCandidate]:
        self._require_scope(scope)
        if limit < 1 or limit > 200:
            raise ValueError("candidate list limit must be between 1 and 200")
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_memory_candidate
                       WHERE org_id=%s AND project_id=%s
                         AND (%s::text IS NULL OR status=%s)
                       ORDER BY updated_at DESC,candidate_id
                       LIMIT %s""",
                    (
                        *scope.key,
                        status.value if status else None,
                        status.value if status else None,
                        limit,
                    ),
                ).fetchall()
                return [self._candidate_from_row(conn, scope, row) for row in rows]
        except (AipMemoryStoreError, ValueError):
            raise
        except Exception as exc:
            raise AipMemoryPersistenceError("candidate list failed") from exc

    def transition_candidate(
        self,
        scope: TenantScope,
        candidate_id: str,
        *,
        to_status: MemoryCandidateStatus,
        expected_version: int,
        actor: str,
        occurred_at: datetime,
        reason_codes: list[str] | None = None,
        governance: GovernanceApprovalRef | None = None,
        evidence_ref: ResourceRef | None = None,
    ) -> MemoryCandidate:
        self._require_scope(scope)
        reasons = reason_codes or []
        if to_status is MemoryCandidateStatus.PROMOTED:
            raise AipMemoryTransitionBlocked(
                "promotion must atomically create a memory item"
            )
        try:
            with self._connect(scope) as conn:
                row = self._candidate_row(conn, scope, candidate_id, for_update=True)
                if row is None:
                    raise AipMemoryNotFound("candidate not found")
                current = MemoryCandidateStatus(row["status"])
                if int(row["version"]) != expected_version:
                    raise AipMemoryConflict("candidate version changed")
                if to_status not in _ALLOWED.get(current, frozenset()):
                    raise AipMemoryTransitionBlocked(
                        f"transition {current.value}->{to_status.value} is blocked"
                    )
                if to_status is MemoryCandidateStatus.QUARANTINED and not reasons:
                    raise AipMemoryTransitionBlocked("quarantine requires reasons")
                if to_status in {MemoryCandidateStatus.APPROVED, MemoryCandidateStatus.PROMOTED} and governance is None:
                    raise AipMemoryTransitionBlocked("approval/promotion requires governance")
                event = self._candidate_event(
                    scope,
                    candidate_id,
                    sequence=self._next_sequence(conn, scope, candidate_id),
                    from_status=current,
                    to_status=to_status,
                    reasons=reasons,
                    evidence_ref=evidence_ref,
                    actor=actor,
                    occurred_at=occurred_at,
                )
                self._insert_event(conn, scope, event)
                updated = conn.execute(
                    """UPDATE aip_memory_candidate SET status=%s,
                       quarantine_reasons=%s::jsonb,eval_report_ref=%s::jsonb,
                       draft_ref=%s::jsonb,approval_event_ref=%s::jsonb,
                       version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND candidate_id=%s
                         AND version=%s RETURNING *""",
                    (
                        to_status.value,
                        self._json(reasons),
                        self._json_nullable(governance.eval_report if governance else None),
                        self._json_nullable(governance.draft if governance else None),
                        self._json_nullable(governance.approval_event if governance else None),
                        occurred_at,
                        *scope.key,
                        candidate_id,
                        expected_version,
                    ),
                ).fetchone()
                if updated is None:
                    raise AipMemoryConflict("candidate changed concurrently")
                conn.commit()
                return self._candidate_from_row(conn, scope, updated)
        except AipMemoryStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPersistenceError("candidate transition failed") from exc

    def list_candidate_events(
        self, scope: TenantScope, candidate_id: str
    ) -> list[MemoryCandidateEvent]:
        self._require_scope(scope)
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_memory_candidate_event
                   WHERE org_id=%s AND project_id=%s AND candidate_id=%s
                   ORDER BY sequence""",
                (*scope.key, candidate_id),
            ).fetchall()
        return [self._event_from_row(scope, row) for row in rows]

    def promote_candidate(
        self,
        scope: TenantScope,
        candidate_id: str,
        *,
        memory_item_id: str,
        expected_version: int,
        actor: str,
        occurred_at: datetime,
        expires_at: datetime | None = None,
    ) -> tuple[MemoryCandidate, MemoryItem, MemoryItemRevision]:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._candidate_row(conn, scope, candidate_id, for_update=True)
                if row is None:
                    raise AipMemoryNotFound("candidate not found")
                if row["status"] == MemoryCandidateStatus.PROMOTED.value:
                    existing = self._item_row(conn, scope, memory_item_id)
                    revision = self._revision_row(conn, scope, memory_item_id, 1)
                    if (
                        existing is None
                        or revision is None
                        or revision["candidate_id"] != candidate_id
                        or revision["created_by"] != actor
                    ):
                        raise AipMemoryConflict("promotion replay does not match item")
                    if expected_version not in {
                        int(row["version"]),
                        int(row["version"]) - 1,
                    }:
                        raise AipMemoryConflict("promotion replay version changed")
                    return (
                        self._candidate_from_row(conn, scope, row),
                        self._item_from_row(scope, existing),
                        self._revision_from_row(scope, revision),
                    )
                if int(row["version"]) != expected_version:
                    raise AipMemoryConflict("candidate version changed")
                if row["status"] != MemoryCandidateStatus.APPROVED.value:
                    raise AipMemoryTransitionBlocked("only approved candidate can promote")
                existing = conn.execute(
                    """SELECT * FROM aip_memory_item
                       WHERE org_id=%s AND project_id=%s AND memory_item_id=%s""",
                    (*scope.key, memory_item_id),
                ).fetchone()
                if existing is not None:
                    raise AipMemoryConflict("memory item already exists")
                payload = ArtifactRef.model_validate(row["payload_ref"])
                if not payload.content_hash:
                    raise AipMemoryTransitionBlocked("promotion requires payload hash")
                conn.execute("SET CONSTRAINTS aip_memory_item_current_revision_fk DEFERRED")
                conn.execute(
                    """INSERT INTO aip_memory_item (
                       org_id,project_id,memory_item_id,memory_layer,scope,status,
                       subject_ref,current_revision,version,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,'active',%s::jsonb,1,1,%s,%s)""",
                    (
                        *scope.key,
                        memory_item_id,
                        row["memory_layer"],
                        row["scope"],
                        self._json(row["subject_ref"]),
                        occurred_at,
                        occurred_at,
                    ),
                )
                source = self._source_row(
                    conn, scope, row["source_id"], row["source_revision"]
                )
                conn.execute(
                    """INSERT INTO aip_memory_item_revision (
                       org_id,project_id,memory_item_id,revision,candidate_id,
                       source_id,source_revision,payload_ref,content_hash,confidence,
                       applicability,markings,effective_at,expires_at,created_by,created_at)
                       VALUES (%s,%s,%s,1,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,
                         %s::jsonb,%s,%s,%s,%s)""",
                    (
                        *scope.key,
                        memory_item_id,
                        candidate_id,
                        row["source_id"],
                        row["source_revision"],
                        self._json(payload),
                        payload.content_hash,
                        row["confidence"],
                        self._json(source["applicability"]),
                        self._json(row["markings"]),
                        occurred_at,
                        expires_at,
                        actor,
                        occurred_at,
                    ),
                )
                event = self._candidate_event(
                    scope,
                    candidate_id,
                    sequence=self._next_sequence(conn, scope, candidate_id),
                    from_status=MemoryCandidateStatus.APPROVED,
                    to_status=MemoryCandidateStatus.PROMOTED,
                    reasons=[],
                    evidence_ref=ResourceRef(
                        resource_type="aip.memory_item",
                        resource_id=memory_item_id,
                        revision="1",
                        authority="postgresql",
                    ),
                    actor=actor,
                    occurred_at=occurred_at,
                )
                self._insert_event(conn, scope, event)
                updated = conn.execute(
                    """UPDATE aip_memory_candidate
                       SET status='promoted',version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND candidate_id=%s
                         AND version=%s RETURNING *""",
                    (occurred_at, *scope.key, candidate_id, expected_version),
                ).fetchone()
                if updated is None:
                    raise AipMemoryConflict("candidate changed concurrently")
                conn.commit()
                return (
                    self._candidate_from_row(conn, scope, updated),
                    self._item_from_row(scope, self._item_row(conn, scope, memory_item_id)),
                    self._revision_from_row(
                        scope, self._revision_row(conn, scope, memory_item_id, 1)
                    ),
                )
        except AipMemoryStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPersistenceError("candidate promotion failed") from exc

    def get_memory_item(
        self, scope: TenantScope, memory_item_id: str
    ) -> tuple[MemoryItem, MemoryItemRevision]:
        self._require_scope(scope)
        with self._connect(scope) as conn:
            row = self._item_row(conn, scope, memory_item_id)
            if row is None:
                raise AipMemoryNotFound("memory item not found")
            revision = self._revision_row(
                conn, scope, memory_item_id, int(row["current_revision"])
            )
            if revision is None:
                raise AipMemoryPersistenceError("current memory revision is missing")
            return self._item_from_row(scope, row), self._revision_from_row(scope, revision)

    def revoke_memory_item(
        self,
        scope: TenantScope,
        memory_item_id: str,
        *,
        expected_version: int,
        reason_code: str,
        actor: str,
        occurred_at: datetime,
    ) -> tuple[MemoryItem, MemoryItemRevision]:
        """CAS-revoke an active item while retaining its immutable revision.

        The deterministic evidence id makes an exact client retry idempotent.
        A changed reason, actor, or expected version is a different command and
        cannot silently reuse the prior revocation.
        """

        self._require_scope(scope)
        reason = reason_code.strip()
        principal = actor.strip()
        if expected_version < 1 or not reason or not principal:
            raise ValueError("expected version, reason code and actor are required")
        command = {
            "memoryItemId": memory_item_id,
            "expectedVersion": expected_version,
            "reasonCode": reason,
            "actor": principal,
        }
        command_hash = hashlib.sha256(
            json.dumps(
                command, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        evidence_id = f"memory-revoke-{command_hash[:40]}"
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    """SELECT * FROM aip_memory_item
                       WHERE org_id=%s AND project_id=%s AND memory_item_id=%s
                       FOR UPDATE""",
                    (*scope.key, memory_item_id),
                ).fetchone()
                if row is None:
                    raise AipMemoryNotFound("memory item not found")
                current_version = int(row["version"])
                if row["status"] == MemoryItemStatus.REVOKED.value:
                    replay = conn.execute(
                        """SELECT content_hash FROM aip_evidence
                           WHERE org_id=%s AND project_id=%s AND evidence_id=%s""",
                        (*scope.key, evidence_id),
                    ).fetchone()
                    if replay is None or replay["content_hash"] != command_hash:
                        raise AipMemoryConflict("memory item was revoked by another command")
                    if current_version != expected_version + 1:
                        raise AipMemoryConflict("memory item version changed")
                    revision = self._revision_row(
                        conn, scope, memory_item_id, int(row["current_revision"])
                    )
                    if revision is None:
                        raise AipMemoryPersistenceError(
                            "current memory revision is missing"
                        )
                    return (
                        self._item_from_row(scope, row),
                        self._revision_from_row(scope, revision),
                    )
                if current_version != expected_version:
                    raise AipMemoryConflict("memory item version changed")
                if row["status"] != MemoryItemStatus.ACTIVE.value:
                    raise AipMemoryTransitionBlocked(
                        f"memory item cannot revoke while {row['status']}"
                    )
                revision = self._revision_row(
                    conn, scope, memory_item_id, int(row["current_revision"])
                )
                if revision is None:
                    raise AipMemoryPersistenceError("current memory revision is missing")
                subject_ref = {
                    "resourceType": "aip.memory_item",
                    "resourceId": memory_item_id,
                    "revision": str(row["current_revision"]),
                    "authority": "postgresql",
                }
                payload = {
                    **command,
                    "newVersion": expected_version + 1,
                    "occurredAt": occurred_at.isoformat(),
                    "contentHash": revision["content_hash"],
                }
                conn.execute(
                    """INSERT INTO aip_evidence (
                       org_id,project_id,evidence_id,run_id,evidence_type,
                       subject_ref,source_type,source_ref,observed_at,freshness_at,
                       content_hash,redaction,payload,created_by,created_at)
                       VALUES (%s,%s,%s,NULL,'memory_revoke',%s::jsonb,
                         'aip-memory-authority',%s,%s,%s,%s,'{}'::jsonb,%s::jsonb,%s,%s)""",
                    (
                        *scope.key,
                        evidence_id,
                        self._json(subject_ref),
                        memory_item_id,
                        occurred_at,
                        occurred_at,
                        command_hash,
                        self._json(payload),
                        principal,
                        occurred_at,
                    ),
                )
                updated = conn.execute(
                    """UPDATE aip_memory_item
                       SET status='revoked',version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND memory_item_id=%s
                         AND status='active' AND version=%s
                       RETURNING *""",
                    (occurred_at, *scope.key, memory_item_id, expected_version),
                ).fetchone()
                if updated is None:
                    raise AipMemoryConflict("memory item changed concurrently")
                conn.commit()
                return (
                    self._item_from_row(scope, updated),
                    self._revision_from_row(scope, revision),
                )
        except (AipMemoryStoreError, ValueError):
            raise
        except Exception as exc:
            raise AipMemoryPersistenceError("memory item revocation failed") from exc

    def list_memory_items(
        self,
        scope: TenantScope,
        *,
        status: MemoryItemStatus | None = None,
        limit: int = 100,
    ) -> list[tuple[MemoryItem, MemoryItemRevision]]:
        self._require_scope(scope)
        if limit < 1 or limit > 200:
            raise ValueError("memory list limit must be between 1 and 200")
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_memory_item
                       WHERE org_id=%s AND project_id=%s
                         AND (%s::text IS NULL OR status=%s)
                       ORDER BY updated_at DESC,memory_item_id
                       LIMIT %s""",
                    (
                        *scope.key,
                        status.value if status else None,
                        status.value if status else None,
                        limit,
                    ),
                ).fetchall()
                result: list[tuple[MemoryItem, MemoryItemRevision]] = []
                for row in rows:
                    revision = self._revision_row(
                        conn, scope, row["memory_item_id"], int(row["current_revision"])
                    )
                    if revision is None:
                        raise AipMemoryPersistenceError(
                            "current memory revision is missing"
                        )
                    result.append(
                        (
                            self._item_from_row(scope, row),
                            self._revision_from_row(scope, revision),
                        )
                    )
                return result
        except (AipMemoryStoreError, ValueError):
            raise
        except Exception as exc:
            raise AipMemoryPersistenceError("memory list failed") from exc

    @staticmethod
    def _require_scope(scope: TenantScope) -> None:
        if not scope.org_id.strip() or not scope.project_id.strip():
            raise ValueError("tenant scope is required")

    def _connect(self, scope: TenantScope):
        return self._connect_factory(scope)

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _json_nullable(cls, value: Any) -> str | None:
        return None if value is None else cls._json(value)

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    def _source_row(self, conn: Any, scope: TenantScope, source_id: str, revision: int):
        return conn.execute(
            """SELECT * FROM aip_memory_source_revision
               WHERE org_id=%s AND project_id=%s AND source_id=%s AND revision=%s""",
            (*scope.key, source_id, revision),
        ).fetchone()

    @staticmethod
    def _source_from_row(row: Any) -> KnowledgeSourceRef:
        return KnowledgeSourceRef(
            source_kind=row["source_kind"],
            source_uri=row["source_uri"],
            source_ref=row["source_ref"],
            observed_at=row["observed_at"],
            freshness_expires_at=row["freshness_expires_at"],
            license_id=row["license_id"],
            usage_policy=row["usage_policy"],
            content_hash=row["content_hash"],
            provider=row["provider"],
            provider_version=row["provider_version"],
            applicability=row["applicability"],
        )

    @staticmethod
    def _candidate_row(conn: Any, scope: TenantScope, candidate_id: str, *, for_update: bool = False):
        suffix = " FOR UPDATE" if for_update else ""
        return conn.execute(
            """SELECT * FROM aip_memory_candidate
               WHERE org_id=%s AND project_id=%s AND candidate_id=%s""" + suffix,
            (*scope.key, candidate_id),
        ).fetchone()

    def _candidate_from_row(self, conn: Any, scope: TenantScope, row: Any) -> MemoryCandidate:
        source_row = self._source_row(conn, scope, row["source_id"], row["source_revision"])
        governance = None
        if row["eval_report_ref"] is not None:
            governance = GovernanceApprovalRef(
                eval_report=row["eval_report_ref"],
                draft=row["draft_ref"],
                approval_event=row["approval_event_ref"],
            )
        request = SubmitMemoryCandidateRequest(
            candidate_layer=row["memory_layer"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            subject=row["subject_ref"],
            payload=row["payload_ref"],
            source=self._source_from_row(source_row),
            confidence=row["confidence"],
            marking=row["markings"],
        )
        return MemoryCandidate(
            tenant=self._tenant(scope),
            candidate_id=row["candidate_id"],
            status=row["status"],
            scope=row["scope"],
            request=request,
            quarantine_reasons=row["quarantine_reasons"],
            governance=governance,
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _require_task_run(conn: Any, scope: TenantScope, task_id: str, run_id: str) -> None:
        row = conn.execute(
            """SELECT task_id FROM aip_task_run
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchone()
        if row is None or row["task_id"] != task_id:
            raise AipMemoryNotFound("task run not found in scope")

    @staticmethod
    def _next_sequence(conn: Any, scope: TenantScope, candidate_id: str) -> int:
        row = conn.execute(
            """SELECT COALESCE(MAX(sequence),0)+1 AS sequence
               FROM aip_memory_candidate_event
               WHERE org_id=%s AND project_id=%s AND candidate_id=%s""",
            (*scope.key, candidate_id),
        ).fetchone()
        return int(row["sequence"])

    def _candidate_event(
        self,
        scope: TenantScope,
        candidate_id: str,
        *,
        sequence: int,
        from_status: MemoryCandidateStatus | None,
        to_status: MemoryCandidateStatus,
        reasons: list[str],
        evidence_ref: ResourceRef | None,
        actor: str,
        occurred_at: datetime,
    ) -> MemoryCandidateEvent:
        stable = {
            "candidateId": candidate_id,
            "sequence": sequence,
            "fromStatus": from_status.value if from_status else None,
            "toStatus": to_status.value,
            "reasonCodes": reasons,
            "evidenceRef": evidence_ref.model_dump(mode="json", by_alias=True) if evidence_ref else None,
            "actor": actor,
            "occurredAt": occurred_at.isoformat(),
        }
        event_hash = hashlib.sha256(self._json(stable).encode()).hexdigest()
        return MemoryCandidateEvent(
            tenant=self._tenant(scope),
            event_id=f"memory-event-{event_hash[:24]}",
            candidate_id=candidate_id,
            sequence=sequence,
            event_type=(
                "submitted"
                if sequence == 1 or to_status is MemoryCandidateStatus.PENDING
                else to_status.value
            ),
            from_status=from_status,
            to_status=to_status,
            reason_codes=reasons,
            evidence_ref=evidence_ref,
            event_hash=event_hash,
            actor=actor,
            occurred_at=occurred_at,
        )

    def _insert_event(self, conn: Any, scope: TenantScope, event: MemoryCandidateEvent) -> None:
        conn.execute(
            """INSERT INTO aip_memory_candidate_event (
               org_id,project_id,event_id,candidate_id,sequence,event_type,
               from_status,to_status,reason_codes,evidence_ref,event_hash,actor,occurred_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)""",
            (
                *scope.key,
                event.event_id,
                event.candidate_id,
                event.sequence,
                event.event_type,
                event.from_status.value if event.from_status else None,
                event.to_status.value,
                self._json(event.reason_codes),
                self._json_nullable(event.evidence_ref),
                event.event_hash,
                event.actor,
                event.occurred_at,
            ),
        )

    def _event_from_row(self, scope: TenantScope, row: Any) -> MemoryCandidateEvent:
        return MemoryCandidateEvent(
            tenant=self._tenant(scope),
            event_id=row["event_id"],
            candidate_id=row["candidate_id"],
            sequence=row["sequence"],
            event_type=row["event_type"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            reason_codes=row["reason_codes"],
            evidence_ref=row["evidence_ref"],
            event_hash=row["event_hash"],
            actor=row["actor"],
            occurred_at=row["occurred_at"],
        )

    @staticmethod
    def _item_row(conn: Any, scope: TenantScope, memory_item_id: str):
        return conn.execute(
            """SELECT * FROM aip_memory_item
               WHERE org_id=%s AND project_id=%s AND memory_item_id=%s""",
            (*scope.key, memory_item_id),
        ).fetchone()

    @staticmethod
    def _revision_row(
        conn: Any, scope: TenantScope, memory_item_id: str, revision: int
    ):
        return conn.execute(
            """SELECT * FROM aip_memory_item_revision
               WHERE org_id=%s AND project_id=%s AND memory_item_id=%s
                 AND revision=%s""",
            (*scope.key, memory_item_id, revision),
        ).fetchone()

    def _item_from_row(self, scope: TenantScope, row: Any) -> MemoryItem:
        return MemoryItem(
            tenant=self._tenant(scope),
            memory_item_id=row["memory_item_id"],
            memory_layer=row["memory_layer"],
            scope=row["scope"],
            status=row["status"],
            subject=row["subject_ref"],
            current_revision=row["current_revision"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _revision_from_row(
        self, scope: TenantScope, row: Any
    ) -> MemoryItemRevision:
        return MemoryItemRevision(
            tenant=self._tenant(scope),
            memory_item_id=row["memory_item_id"],
            revision=row["revision"],
            candidate_id=row["candidate_id"],
            source_id=row["source_id"],
            source_revision=row["source_revision"],
            payload=row["payload_ref"],
            content_hash=row["content_hash"],
            confidence=row["confidence"],
            applicability=row["applicability"],
            markings=row["markings"],
            effective_at=row["effective_at"],
            expires_at=row["expires_at"],
            created_by=row["created_by"],
            created_at=row["created_at"],
        )


__all__ = [
    "AipMemoryConflict",
    "AipMemoryNotFound",
    "AipMemoryPersistenceError",
    "AipMemoryStore",
    "AipMemoryStoreError",
    "AipMemoryTransitionBlocked",
]
