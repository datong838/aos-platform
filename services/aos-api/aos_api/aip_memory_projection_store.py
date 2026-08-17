"""Transactional PostgreSQL authority for AIP-5 E7 memory projections.

The store persists references and governance metadata only.  Memory payloads
remain in the AIP-5 Memory authority and agent identity remains in AIP-6.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from aos_api.aip_agent_registry_contracts import AgentInstanceStatus
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_contracts import TenantContext
from aos_api.aip_memory_projection_contracts import (
    ChangeMemoryProjectionStatusRequest,
    CreateMemoryProjectionRequest,
    MemoryProjection,
    MemoryProjectionEvent,
    MemoryProjectionEventType,
    MemoryProjectionExactRef,
    MemoryProjectionReceipt,
    MemoryProjectionStatus,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipMemoryProjectionError(RuntimeError):
    code = "AIP_MEMORY_PROJECTION_ERROR"


class AipMemoryProjectionNotFound(AipMemoryProjectionError):
    code = "AIP_MEMORY_PROJECTION_NOT_FOUND"


class AipMemoryProjectionConflict(AipMemoryProjectionError):
    code = "AIP_MEMORY_PROJECTION_CONFLICT"


class AipMemoryProjectionBlocked(AipMemoryProjectionError):
    code = "AIP_MEMORY_PROJECTION_BLOCKED"


class AipMemoryProjectionPersistenceError(AipMemoryProjectionError):
    code = "AIP_MEMORY_PROJECTION_PERSISTENCE_ERROR"


class AipMemoryProjectionStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create_projection(
        self,
        scope: TenantScope,
        request: CreateMemoryProjectionRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> tuple[MemoryProjection, MemoryProjectionReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        operation = "create"
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    projection = self._projection_by_id(
                        conn, scope, replay["projection_id"]
                    )
                    return projection, self._receipt_from_row(scope, replay)
                if self._projection_row(conn, scope, request.projection_id) is not None:
                    raise AipMemoryProjectionConflict("projection id already exists")

                self._require_exact_instance(
                    conn, scope, request.owner_instance_ref, lock=True
                )
                for recipient in request.recipient_instance_refs:
                    self._require_exact_instance(conn, scope, recipient, lock=True)
                self._require_exact_memory(
                    conn,
                    scope,
                    request.memory_ref.memory_item_id,
                    request.memory_ref.revision,
                    request.memory_ref.content_hash,
                    allowed_purposes=request.allowed_purposes,
                    allowed_markings=request.allowed_markings,
                    effective_at=request.effective_at,
                    expires_at=request.expires_at,
                    lock=True,
                )
                content_hash = self._hash(
                    self._projection_snapshot(request, MemoryProjectionStatus.ACTIVE, 1)
                )
                conn.execute(
                    """INSERT INTO aip_memory_agent_projection (
                       org_id,project_id,projection_id,kind,owner_instance_id,
                       owner_instance_version,owner_instance_hash,owner_instance_ref,
                       memory_item_id,memory_revision,memory_hash,memory_ref,
                       allowed_purposes,allowed_markings,disclosure,status,version,
                       content_hash,effective_at,expires_at,created_by,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,
                         %s::jsonb,%s::jsonb,%s,'active',1,%s,%s,%s,%s,%s,%s)""",
                    (
                        *scope.key,
                        request.projection_id,
                        request.kind.value,
                        request.owner_instance_ref.asset_id,
                        request.owner_instance_ref.revision,
                        request.owner_instance_ref.content_hash,
                        self._json(request.owner_instance_ref),
                        request.memory_ref.memory_item_id,
                        request.memory_ref.revision,
                        request.memory_ref.content_hash,
                        self._json(request.memory_ref),
                        self._json(request.allowed_purposes),
                        self._json(request.allowed_markings),
                        request.disclosure.value,
                        content_hash,
                        request.effective_at,
                        request.expires_at,
                        actor.strip(),
                        occurred_at,
                        occurred_at,
                    ),
                )
                for recipient in request.recipient_instance_refs:
                    conn.execute(
                        """INSERT INTO aip_memory_agent_projection_recipient (
                           org_id,project_id,projection_id,recipient_instance_id,
                           recipient_instance_version,recipient_instance_hash,
                           recipient_instance_ref,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                        (
                            *scope.key,
                            request.projection_id,
                            recipient.asset_id,
                            recipient.revision,
                            recipient.content_hash,
                            self._json(recipient),
                            occurred_at,
                        ),
                    )
                projection_ref = MemoryProjectionExactRef(
                    projection_id=request.projection_id,
                    version=1,
                    content_hash=content_hash,
                )
                self._insert_event(
                    conn,
                    scope,
                    projection_ref,
                    sequence=1,
                    event_type=MemoryProjectionEventType.CREATED,
                    from_status=None,
                    to_status=MemoryProjectionStatus.ACTIVE,
                    reason_hash=self._hash("created"),
                    actor=actor,
                    occurred_at=occurred_at,
                )
                receipt_row = self._insert_receipt(
                    conn,
                    scope,
                    operation,
                    idempotency_key,
                    request_hash,
                    projection_ref,
                    actor,
                    occurred_at,
                )
                projection = self._projection_by_id(conn, scope, request.projection_id)
                conn.commit()
                return projection, self._receipt_from_row(scope, receipt_row)
        except AipMemoryProjectionError:
            raise
        except Exception as exc:
            raise AipMemoryProjectionPersistenceError(
                "memory projection persistence failed"
            ) from exc

    def get_projection(
        self, scope: TenantScope, projection_id: str
    ) -> MemoryProjection:
        self._require_scope(scope)
        try:
            with self._connect_factory(scope) as conn:
                return self._projection_by_id(conn, scope, projection_id)
        except AipMemoryProjectionError:
            raise
        except Exception as exc:
            raise AipMemoryProjectionPersistenceError(
                "memory projection read failed"
            ) from exc

    def list_projections(
        self,
        scope: TenantScope,
        *,
        owner_instance_id: str | None = None,
        recipient_instance_id: str | None = None,
        limit: int = 100,
    ) -> list[MemoryProjection]:
        self._require_scope(scope)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """SELECT DISTINCT p.* FROM aip_memory_agent_projection p
                       LEFT JOIN aip_memory_agent_projection_recipient r
                         ON r.org_id=p.org_id AND r.project_id=p.project_id
                        AND r.projection_id=p.projection_id
                       WHERE p.org_id=%s AND p.project_id=%s
                         AND (%s::text IS NULL OR p.owner_instance_id=%s)
                         AND (%s::text IS NULL OR r.recipient_instance_id=%s)
                       ORDER BY p.updated_at DESC,p.projection_id LIMIT %s""",
                    (
                        *scope.key,
                        owner_instance_id,
                        owner_instance_id,
                        recipient_instance_id,
                        recipient_instance_id,
                        limit,
                    ),
                ).fetchall()
                return [self._projection_from_row(conn, scope, row) for row in rows]
        except Exception as exc:
            raise AipMemoryProjectionPersistenceError(
                "memory projection list failed"
            ) from exc

    def change_status(
        self,
        scope: TenantScope,
        projection_id: str,
        request: ChangeMemoryProjectionStatusRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> tuple[MemoryProjection, MemoryProjectionReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        operation = {
            MemoryProjectionStatus.ACTIVE: "reactivate",
            MemoryProjectionStatus.SUSPENDED: "suspend",
            MemoryProjectionStatus.REVOKED: "revoke",
        }[request.to_status]
        request_hash = self._command_hash(
            {"projectionId": projection_id, "request": request}, actor
        )
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    projection = self._projection_by_id(
                        conn, scope, replay["projection_id"]
                    )
                    return projection, self._receipt_from_row(scope, replay)
                row = self._projection_row(conn, scope, projection_id, lock=True)
                if row is None:
                    raise AipMemoryProjectionNotFound("projection not found")
                if int(row["version"]) != request.expected_version:
                    raise AipMemoryProjectionConflict("projection version conflict")
                if MemoryProjectionStatus(row["status"]) is not request.from_status:
                    raise AipMemoryProjectionConflict("projection status drifted")
                if request.to_status is MemoryProjectionStatus.ACTIVE:
                    self._revalidate_row_dependencies(conn, scope, row, occurred_at)
                new_version = int(row["version"]) + 1
                recipient_refs = [
                    recipient["recipient_instance_ref"]
                    for recipient in self._recipient_rows(
                        conn, scope, row["projection_id"]
                    )
                ]
                new_hash = self._hash(
                    self._row_snapshot(
                        row,
                        request.to_status,
                        new_version,
                        recipient_refs=recipient_refs,
                    )
                )
                updated = conn.execute(
                    """UPDATE aip_memory_agent_projection
                       SET status=%s,version=%s,content_hash=%s,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND projection_id=%s
                         AND version=%s AND status=%s RETURNING *""",
                    (
                        request.to_status.value,
                        new_version,
                        new_hash,
                        occurred_at,
                        *scope.key,
                        projection_id,
                        request.expected_version,
                        request.from_status.value,
                    ),
                ).fetchone()
                if updated is None:
                    raise AipMemoryProjectionConflict("projection CAS failed")
                projection_ref = MemoryProjectionExactRef(
                    projection_id=projection_id,
                    version=new_version,
                    content_hash=new_hash,
                )
                event_type = {
                    MemoryProjectionStatus.SUSPENDED: MemoryProjectionEventType.SUSPENDED,
                    MemoryProjectionStatus.ACTIVE: MemoryProjectionEventType.REACTIVATED,
                    MemoryProjectionStatus.REVOKED: MemoryProjectionEventType.REVOKED,
                }[request.to_status]
                sequence = int(
                    conn.execute(
                        """SELECT COALESCE(MAX(sequence),0)+1 AS n
                           FROM aip_memory_agent_projection_event
                           WHERE org_id=%s AND project_id=%s AND projection_id=%s""",
                        (*scope.key, projection_id),
                    ).fetchone()["n"]
                )
                self._insert_event(
                    conn,
                    scope,
                    projection_ref,
                    sequence=sequence,
                    event_type=event_type,
                    from_status=request.from_status,
                    to_status=request.to_status,
                    reason_hash=request.reason_hash,
                    actor=actor,
                    occurred_at=occurred_at,
                )
                receipt_row = self._insert_receipt(
                    conn,
                    scope,
                    operation,
                    idempotency_key,
                    request_hash,
                    projection_ref,
                    actor,
                    occurred_at,
                )
                projection = self._projection_from_row(conn, scope, updated)
                conn.commit()
                return projection, self._receipt_from_row(scope, receipt_row)
        except AipMemoryProjectionError:
            raise
        except Exception as exc:
            raise AipMemoryProjectionPersistenceError(
                "memory projection status update failed"
            ) from exc

    def list_events(
        self, scope: TenantScope, projection_id: str
    ) -> list[MemoryProjectionEvent]:
        self._require_scope(scope)
        try:
            with self._connect_factory(scope) as conn:
                if self._projection_row(conn, scope, projection_id) is None:
                    raise AipMemoryProjectionNotFound("projection not found")
                rows = conn.execute(
                    """SELECT e.*,
                         (SELECT COUNT(*) FROM aip_memory_agent_projection_receipt r
                           WHERE r.org_id=e.org_id AND r.project_id=e.project_id
                             AND r.projection_id=e.projection_id
                             AND r.projection_version=e.projection_version)
                           AS receipt_count,
                         (SELECT MIN(r.projection_hash)
                            FROM aip_memory_agent_projection_receipt r
                           WHERE r.org_id=e.org_id AND r.project_id=e.project_id
                             AND r.projection_id=e.projection_id
                             AND r.projection_version=e.projection_version)
                           AS projection_hash
                       FROM aip_memory_agent_projection_event e
                       WHERE e.org_id=%s AND e.project_id=%s AND e.projection_id=%s
                       ORDER BY e.sequence""",
                    (*scope.key, projection_id),
                ).fetchall()
                if any(int(row["receipt_count"]) != 1 for row in rows):
                    raise AipMemoryProjectionConflict(
                        "projection event receipt cardinality drifted"
                    )
                return [self._event_from_row(scope, row) for row in rows]
        except AipMemoryProjectionError:
            raise
        except Exception as exc:
            raise AipMemoryProjectionPersistenceError(
                "memory projection event read failed"
            ) from exc

    def _require_exact_instance(self, conn, scope, ref, *, lock: bool) -> None:
        clause = " FOR SHARE OF i,t" if lock else ""
        row = conn.execute(
            """SELECT i.*,t.content_hash FROM aip_agent_instance i
               JOIN aip_agent_template_revision t ON t.template_id=i.template_id
                AND t.revision=i.template_revision
               WHERE i.org_id=%s AND i.project_id=%s AND i.instance_id=%s"""
            + clause,
            (*scope.key, ref.asset_id),
        ).fetchone()
        if row is None:
            raise AipMemoryProjectionNotFound("exact agent instance not found")
        instance = AipAgentRegistryStore._instance_from_row(scope, row)
        if instance.instance_ref != ref:
            raise AipMemoryProjectionConflict("agent instance version/hash drifted")
        if instance.status is not AgentInstanceStatus.ACTIVE:
            raise AipMemoryProjectionBlocked("agent instance is not active")

    def _require_exact_memory(
        self,
        conn,
        scope,
        memory_item_id,
        revision,
        content_hash,
        *,
        allowed_purposes,
        allowed_markings,
        effective_at,
        expires_at,
        lock,
    ) -> None:
        clause = " FOR SHARE OF i,r,s" if lock else ""
        row = conn.execute(
            """SELECT i.status AS item_status,i.current_revision,
                      r.content_hash,r.applicability,r.markings,r.effective_at,
                      r.expires_at,s.freshness_expires_at
               FROM aip_memory_item i
               JOIN aip_memory_item_revision r ON r.org_id=i.org_id
                AND r.project_id=i.project_id AND r.memory_item_id=i.memory_item_id
               JOIN aip_memory_source_revision s ON s.org_id=r.org_id
                AND s.project_id=r.project_id AND s.source_id=r.source_id
                AND s.revision=r.source_revision
               WHERE i.org_id=%s AND i.project_id=%s AND i.memory_item_id=%s
                 AND r.revision=%s"""
            + clause,
            (*scope.key, memory_item_id, revision),
        ).fetchone()
        if row is None:
            raise AipMemoryProjectionNotFound("exact memory revision not found")
        if row["content_hash"] != content_hash:
            raise AipMemoryProjectionConflict("memory revision hash drifted")
        if row["item_status"] != "active" or int(row["current_revision"]) != revision:
            raise AipMemoryProjectionBlocked("memory item is not current and active")
        if effective_at < row["effective_at"]:
            raise AipMemoryProjectionBlocked("projection predates memory effectiveness")
        upper = row["freshness_expires_at"]
        if row["expires_at"] is not None:
            upper = min(upper, row["expires_at"])
        if expires_at > upper:
            raise AipMemoryProjectionBlocked(
                "projection exceeds memory/source validity"
            )
        if not set(allowed_markings).issubset(set(row["markings"])):
            raise AipMemoryProjectionBlocked(
                "projection markings exceed memory markings"
            )
        if not set(allowed_purposes).issubset(set(row["applicability"])):
            raise AipMemoryProjectionBlocked(
                "projection purposes exceed memory applicability"
            )

    def _revalidate_row_dependencies(self, conn, scope, row, occurred_at) -> None:
        if occurred_at < row["effective_at"] or occurred_at >= row["expires_at"]:
            raise AipMemoryProjectionBlocked(
                "projection is outside its effective interval"
            )
        owner = row["owner_instance_ref"]
        from aos_api.aip_agent_registry_contracts import VersionedAssetRef

        self._require_exact_instance(
            conn, scope, VersionedAssetRef.model_validate(owner), lock=True
        )
        recipients = self._recipient_rows(conn, scope, row["projection_id"])
        for recipient in recipients:
            self._require_exact_instance(
                conn,
                scope,
                VersionedAssetRef.model_validate(recipient["recipient_instance_ref"]),
                lock=True,
            )
        self._require_exact_memory(
            conn,
            scope,
            row["memory_item_id"],
            int(row["memory_revision"]),
            row["memory_hash"],
            allowed_purposes=row["allowed_purposes"],
            allowed_markings=row["allowed_markings"],
            effective_at=max(row["effective_at"], occurred_at),
            expires_at=row["expires_at"],
            lock=True,
        )

    def _projection_by_id(self, conn, scope, projection_id) -> MemoryProjection:
        row = self._projection_row(conn, scope, projection_id)
        if row is None:
            raise AipMemoryProjectionNotFound("projection not found")
        return self._projection_from_row(conn, scope, row)

    @staticmethod
    def _projection_row(conn, scope, projection_id, *, lock=False):
        suffix = " FOR UPDATE" if lock else ""
        return conn.execute(
            """SELECT * FROM aip_memory_agent_projection
               WHERE org_id=%s AND project_id=%s AND projection_id=%s"""
            + suffix,
            (*scope.key, projection_id),
        ).fetchone()

    @staticmethod
    def _recipient_rows(conn, scope, projection_id):
        return conn.execute(
            """SELECT * FROM aip_memory_agent_projection_recipient
               WHERE org_id=%s AND project_id=%s AND projection_id=%s
               ORDER BY recipient_instance_id,recipient_instance_version""",
            (*scope.key, projection_id),
        ).fetchall()

    def _projection_from_row(self, conn, scope, row) -> MemoryProjection:
        from aos_api.aip_agent_registry_contracts import VersionedAssetRef
        from aos_api.aip_memory_projection_contracts import MemoryRevisionExactRef

        recipients = [
            VersionedAssetRef.model_validate(value["recipient_instance_ref"])
            for value in self._recipient_rows(conn, scope, row["projection_id"])
        ]
        return MemoryProjection(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            projection_ref=MemoryProjectionExactRef(
                projection_id=row["projection_id"],
                version=int(row["version"]),
                content_hash=row["content_hash"],
            ),
            kind=row["kind"],
            owner_instance_ref=VersionedAssetRef.model_validate(
                row["owner_instance_ref"]
            ),
            memory_ref=MemoryRevisionExactRef.model_validate(row["memory_ref"]),
            recipient_instance_refs=recipients,
            allowed_purposes=row["allowed_purposes"],
            allowed_markings=row["allowed_markings"],
            disclosure=row["disclosure"],
            status=row["status"],
            effective_at=row["effective_at"],
            expires_at=row["expires_at"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _insert_event(
        self,
        conn,
        scope,
        projection_ref,
        *,
        sequence,
        event_type,
        from_status,
        to_status,
        reason_hash,
        actor,
        occurred_at,
    ) -> None:
        payload = {
            "projectionRef": projection_ref.model_dump(mode="json", by_alias=True),
            "sequence": sequence,
            "eventType": event_type.value,
            "fromStatus": from_status.value if from_status else None,
            "toStatus": to_status.value,
            "reasonHash": reason_hash,
            "actor": actor.strip(),
            "occurredAt": occurred_at.isoformat(),
        }
        conn.execute(
            """INSERT INTO aip_memory_agent_projection_event (
               org_id,project_id,event_id,projection_id,projection_version,
               sequence,event_type,from_status,to_status,reason_hash,event_hash,
               actor,occurred_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                f"aip5e7e-{uuid.uuid4().hex}",
                projection_ref.projection_id,
                projection_ref.version,
                sequence,
                event_type.value,
                from_status.value if from_status else None,
                to_status.value,
                reason_hash,
                self._hash(payload),
                actor.strip(),
                occurred_at,
            ),
        )

    def _insert_receipt(
        self,
        conn,
        scope,
        operation,
        key,
        request_hash,
        projection_ref,
        actor,
        occurred_at,
    ):
        return conn.execute(
            """INSERT INTO aip_memory_agent_projection_receipt (
               org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
               projection_id,projection_version,projection_hash,actor,created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (
                *scope.key,
                f"aip5e7r-{uuid.uuid4().hex}",
                operation,
                key.strip(),
                request_hash,
                projection_ref.projection_id,
                projection_ref.version,
                projection_ref.content_hash,
                actor.strip(),
                occurred_at,
            ),
        ).fetchone()

    @staticmethod
    def _receipt_row(conn, scope, operation, key):
        return conn.execute(
            """SELECT * FROM aip_memory_agent_projection_receipt
               WHERE org_id=%s AND project_id=%s AND operation=%s
                 AND idempotency_key=%s""",
            (*scope.key, operation, key.strip()),
        ).fetchone()

    @staticmethod
    def _receipt_from_row(scope, row) -> MemoryProjectionReceipt:
        return MemoryProjectionReceipt(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            receipt_id=row["receipt_id"],
            operation=row["operation"],
            idempotency_key=row["idempotency_key"],
            request_hash=row["request_hash"],
            result_ref=MemoryProjectionExactRef(
                projection_id=row["projection_id"],
                version=int(row["projection_version"]),
                content_hash=row["projection_hash"],
            ),
            actor=row["actor"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _event_from_row(scope, row) -> MemoryProjectionEvent:
        return MemoryProjectionEvent(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            event_id=row["event_id"],
            projection_ref=MemoryProjectionExactRef(
                projection_id=row["projection_id"],
                version=int(row["projection_version"]),
                content_hash=row["projection_hash"],
            ),
            sequence=int(row["sequence"]),
            event_type=row["event_type"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            reason_hash=row["reason_hash"],
            event_hash=row["event_hash"],
            actor=row["actor"],
            occurred_at=row["occurred_at"],
        )

    @staticmethod
    def _projection_snapshot(request, status, version):
        return {
            **request.model_dump(mode="json", by_alias=True),
            "status": status.value,
            "version": version,
        }

    @staticmethod
    def _row_snapshot(row, status, version, *, recipient_refs):
        return {
            "projectionId": row["projection_id"],
            "kind": row["kind"],
            "ownerInstanceRef": row["owner_instance_ref"],
            "memoryRef": row["memory_ref"],
            "recipientInstanceRefs": recipient_refs,
            "allowedPurposes": row["allowed_purposes"],
            "allowedMarkings": row["allowed_markings"],
            "disclosure": row["disclosure"],
            "effectiveAt": row["effective_at"].isoformat(),
            "expiresAt": row["expires_at"].isoformat(),
            "status": status.value,
            "version": version,
        }

    @classmethod
    def _command_hash(cls, request, actor):
        value = request
        if hasattr(request, "model_dump"):
            value = request.model_dump(mode="json", by_alias=True)
        elif isinstance(request, dict):
            value = {
                key: (
                    child.model_dump(mode="json", by_alias=True)
                    if hasattr(child, "model_dump")
                    else child
                )
                for key, child in request.items()
            }
        return cls._hash({"actor": actor.strip(), "request": value})

    @classmethod
    def _hash(cls, value):
        return hashlib.sha256(cls._json(value).encode()).hexdigest()

    @staticmethod
    def _json(value):
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _lock(conn, scope, operation, key):
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"aip5e7:{scope.org_id}:{scope.project_id}:{operation}:{key}",),
        )

    @staticmethod
    def _require_replay_hash(row, expected):
        if row["request_hash"] != expected:
            raise AipMemoryProjectionConflict(
                "idempotency key was reused with different content"
            )

    @staticmethod
    def _require_scope(scope):
        if not scope.org_id or not scope.project_id:
            raise ValueError("tenant scope is required")

    @classmethod
    def _validate_command(cls, scope, key, actor):
        cls._require_scope(scope)
        if not key.strip() or not actor.strip():
            raise ValueError("idempotency key and actor are required")


__all__ = [
    "AipMemoryProjectionBlocked",
    "AipMemoryProjectionConflict",
    "AipMemoryProjectionError",
    "AipMemoryProjectionNotFound",
    "AipMemoryProjectionPersistenceError",
    "AipMemoryProjectionStore",
]
