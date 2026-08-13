"""PostgreSQL authority for AIP-6 agent instances and durable receipts."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    AgentInstance,
    AgentInstanceStatus,
    AgentTemplateRevision,
    CreateAgentInstanceRequest,
    PublishAgentTemplateRequest,
    RegistryReceipt,
    TemplateLifecycle,
    UpdateAgentInstanceRequest,
    VersionedAssetRef,
)
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipAgentRegistryError(RuntimeError):
    code = "AIP_AGENT_REGISTRY_ERROR"


class AipAgentRegistryNotFound(AipAgentRegistryError):
    code = "AIP_AGENT_REGISTRY_NOT_FOUND"


class AipAgentRegistryConflict(AipAgentRegistryError):
    code = "AIP_AGENT_REGISTRY_CONFLICT"


class AipAgentRegistryTransitionBlocked(AipAgentRegistryError):
    code = "AIP_AGENT_REGISTRY_TRANSITION_BLOCKED"


class AipAgentRegistryPersistenceError(AipAgentRegistryError):
    code = "AIP_AGENT_REGISTRY_PERSISTENCE_ERROR"


_INSTANCE_TRANSITIONS = {
    AgentInstanceStatus.PROVISIONING: {AgentInstanceStatus.ACTIVE, AgentInstanceStatus.DELETED},
    AgentInstanceStatus.ACTIVE: {AgentInstanceStatus.SUSPENDED, AgentInstanceStatus.DELETED},
    AgentInstanceStatus.SUSPENDED: {AgentInstanceStatus.ACTIVE, AgentInstanceStatus.DELETED},
    AgentInstanceStatus.DELETED: set(),
}


class AipAgentRegistryStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish_template(self, request: PublishAgentTemplateRequest, *, actor: str) -> AgentTemplateRevision:
        if not actor.strip():
            raise ValueError("actor is required")
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """INSERT INTO aip_agent_template_revision
                       (template_id,revision,display_name,role_key,lifecycle,source_ref,
                        source_license,manifest,content_hash,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s)
                       ON CONFLICT (template_id,revision) DO NOTHING RETURNING *""",
                    (request.template_id, request.revision, request.display_name,
                     request.role_key, request.lifecycle.value, self._json(request.source_ref),
                     request.source_license, self._json(request.manifest), request.content_hash,
                     actor.strip()),
                ).fetchone()
                if row is None:
                    row = self._template_row(conn, request.template_id, request.revision)
                    if row is None or self._template_from_row(row).model_dump() != AgentTemplateRevision(
                        **request.model_dump(), created_by=row["created_by"], created_at=row["created_at"]
                    ).model_dump():
                        raise AipAgentRegistryConflict("template revision already has different content")
                conn.commit()
                return self._template_from_row(row)
        except AipAgentRegistryError:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent template persistence failed") from exc

    def get_template(self, template_id: str, revision: int) -> AgentTemplateRevision:
        try:
            with self._connect_factory() as conn:
                row = self._template_row(conn, template_id, revision)
                if row is None:
                    raise AipAgentRegistryNotFound("agent template revision not found")
                return self._template_from_row(row)
        except AipAgentRegistryError:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent template read failed") from exc

    def create_instance(self, scope: TenantScope, request: CreateAgentInstanceRequest, *, idempotency_key: str, actor: str, occurred_at: datetime) -> tuple[AgentInstance, RegistryReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        request_hash = self._command_hash(request, actor)
        operation = "agent_instance.create"
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    instance = self._instance_from_row(scope, self._instance_row(conn, scope, replay["result_ref"]["resourceId"]))
                    return instance, self._receipt_from_row(scope, replay)
                template = conn.execute(
                    """SELECT * FROM aip_agent_template_revision
                       WHERE template_id=%s AND revision=%s AND content_hash=%s""",
                    (request.template.asset_id, request.template.revision, request.template.content_hash),
                ).fetchone()
                if template is None:
                    raise AipAgentRegistryNotFound("exact agent template revision not found")
                if TemplateLifecycle(template["lifecycle"]) is not TemplateLifecycle.PUBLISHED:
                    raise AipAgentRegistryTransitionBlocked("only published templates can be instantiated")
                latest = conn.execute(
                    """SELECT lifecycle FROM aip_agent_template_revision
                       WHERE template_id=%s ORDER BY revision DESC LIMIT 1""",
                    (request.template.asset_id,),
                ).fetchone()
                if latest is None or TemplateLifecycle(latest["lifecycle"]) is not TemplateLifecycle.PUBLISHED:
                    raise AipAgentRegistryTransitionBlocked(
                        "deprecated or revoked template families cannot create instances"
                    )
                if self._instance_row(conn, scope, request.instance_id) is not None:
                    raise AipAgentRegistryConflict("agent instance id already exists")
                row = conn.execute(
                    """INSERT INTO aip_agent_instance
                       (org_id,project_id,instance_id,template_id,template_revision,status,
                        overlay,version,created_by,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,1,%s,%s,%s) RETURNING *""",
                    (*scope.key, request.instance_id, request.template.asset_id,
                     request.template.revision, request.initial_status.value,
                     self._json(request.overlay), actor.strip(), occurred_at, occurred_at),
                ).fetchone()
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key,
                    request_hash, "AgentTemplate", request.template.asset_id,
                    "AgentInstance", request.instance_id, actor, occurred_at)
                row = self._instance_row(conn, scope, request.instance_id)
                conn.commit()
                return self._instance_from_row(scope, row), receipt
        except AipAgentRegistryError:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent instance persistence failed") from exc

    def get_instance(self, scope: TenantScope, instance_id: str) -> AgentInstance:
        try:
            with self._connect_factory(scope) as conn:
                row = self._instance_row(conn, scope, instance_id)
                if row is None:
                    raise AipAgentRegistryNotFound("agent instance not found")
                return self._instance_from_row(scope, row)
        except AipAgentRegistryError:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent instance read failed") from exc

    def list_instances(self, scope: TenantScope, *, limit: int = 100) -> list[AgentInstance]:
        if limit < 1 or limit > 200:
            raise ValueError("list limit must be between 1 and 200")
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """SELECT i.*,t.content_hash FROM aip_agent_instance i
                       JOIN aip_agent_template_revision t ON t.template_id=i.template_id
                        AND t.revision=i.template_revision
                       WHERE i.org_id=%s AND i.project_id=%s
                       ORDER BY i.updated_at DESC,i.instance_id LIMIT %s""", (*scope.key, limit)
                ).fetchall()
                return [self._instance_from_row(scope, row) for row in rows]
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent instance list failed") from exc

    def update_instance(self, scope: TenantScope, instance_id: str, request: UpdateAgentInstanceRequest, *, idempotency_key: str, actor: str, occurred_at: datetime) -> tuple[AgentInstance, RegistryReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        request_hash = self._command_hash(request, actor)
        operation = "agent_instance.update"
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    return self._instance_from_row(scope, self._instance_row(conn, scope, instance_id)), self._receipt_from_row(scope, replay)
                if request.to_status not in _INSTANCE_TRANSITIONS[request.from_status]:
                    raise AipAgentRegistryTransitionBlocked("agent instance transition is not allowed")
                row = conn.execute(
                    """UPDATE aip_agent_instance SET status=%s,overlay=%s::jsonb,
                       version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND instance_id=%s
                        AND version=%s AND status=%s RETURNING *""",
                    (request.to_status.value, self._json(request.overlay), occurred_at,
                     *scope.key, instance_id, request.expected_version, request.from_status.value),
                ).fetchone()
                if row is None:
                    if self._instance_row(conn, scope, instance_id) is None:
                        raise AipAgentRegistryNotFound("agent instance not found")
                    raise AipAgentRegistryConflict("agent instance version or status changed")
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key,
                    request_hash, "AgentInstance", instance_id, "AgentInstance", instance_id,
                    actor, occurred_at)
                row = self._instance_row(conn, scope, instance_id)
                conn.commit()
                return self._instance_from_row(scope, row), receipt
        except AipAgentRegistryError:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent instance update failed") from exc

    @staticmethod
    def _template_row(conn: Any, template_id: str, revision: int):
        return conn.execute("SELECT * FROM aip_agent_template_revision WHERE template_id=%s AND revision=%s", (template_id, revision)).fetchone()

    @staticmethod
    def _instance_row(conn: Any, scope: TenantScope, instance_id: str):
        return conn.execute(
            """SELECT i.*,t.content_hash FROM aip_agent_instance i
               JOIN aip_agent_template_revision t ON t.template_id=i.template_id
                AND t.revision=i.template_revision
               WHERE i.org_id=%s AND i.project_id=%s AND i.instance_id=%s""",
            (*scope.key, instance_id),
        ).fetchone()

    @staticmethod
    def _receipt_row(conn: Any, scope: TenantScope, operation: str, key: str):
        return conn.execute("""SELECT * FROM aip_agent_registry_receipt
            WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s""",
            (*scope.key, operation, key)).fetchone()

    def _insert_receipt(self, conn: Any, scope: TenantScope, operation: str, key: str,
                        request_hash: str, source_type: str, source_id: str,
                        result_type: str, result_id: str, actor: str,
                        occurred_at: datetime) -> RegistryReceipt:
        row = conn.execute("""INSERT INTO aip_agent_registry_receipt
            (org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
             resource_ref,result_ref,status,created_by,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,'applied',%s,%s) RETURNING *""",
            (*scope.key, f"aip6r-{uuid.uuid4().hex}", operation, key, request_hash,
             self._json(self._ref(source_type, source_id)), self._json(self._ref(result_type, result_id)),
             actor.strip(), occurred_at)).fetchone()
        return self._receipt_from_row(scope, row)

    @staticmethod
    def _ref(kind: str, identifier: str) -> ResourceRef:
        return ResourceRef(resource_type=kind, resource_id=identifier, revision=None, authority="postgresql")

    @staticmethod
    def _template_from_row(row: Any) -> AgentTemplateRevision:
        return AgentTemplateRevision(template_id=row["template_id"], revision=row["revision"],
            display_name=row["display_name"], role_key=row["role_key"], lifecycle=row["lifecycle"],
            source_ref=row["source_ref"], source_license=row["source_license"], manifest=row["manifest"],
            content_hash=row["content_hash"], created_by=row["created_by"], created_at=row["created_at"])

    @classmethod
    def _instance_from_row(cls, scope: TenantScope, row: Any) -> AgentInstance:
        if row is None:
            raise AipAgentRegistryNotFound("agent instance not found")
        snapshot = cls._instance_snapshot(row)
        return AgentInstance(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            instance_id=row["instance_id"], instance_ref=VersionedAssetRef(asset_type="AgentInstance",
            asset_id=row["instance_id"], revision=row["version"], content_hash=cls._hash(snapshot)),
            template=VersionedAssetRef(asset_type="AgentTemplate",
            asset_id=row["template_id"], revision=row["template_revision"], content_hash=row["content_hash"]),
            status=row["status"], overlay=row["overlay"], version=row["version"], created_by=row["created_by"],
            created_at=row["created_at"], updated_at=row["updated_at"])

    @staticmethod
    def _receipt_from_row(scope: TenantScope, row: Any) -> RegistryReceipt:
        return RegistryReceipt(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            receipt_id=row["receipt_id"], operation=row["operation"], idempotency_key=row["idempotency_key"],
            request_hash=row["request_hash"], resource_ref=row["resource_ref"], result_ref=row["result_ref"],
            status=row["status"], created_by=row["created_by"], created_at=row["created_at"])

    @staticmethod
    def _json(value: Any) -> str:
        def normalize(item: Any) -> Any:
            if hasattr(item, "model_dump"):
                return normalize(item.model_dump(mode="json", by_alias=True))
            if isinstance(item, dict):
                return {key: normalize(child) for key, child in item.items()}
            if isinstance(item, (list, tuple)):
                return [normalize(child) for child in item]
            return item

        return json.dumps(
            normalize(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @classmethod
    def _hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode()).hexdigest()

    @classmethod
    def _instance_snapshot(cls, row: Any) -> dict[str, Any]:
        return {
            "instanceId": row["instance_id"],
            "template": {
                "assetType": "AgentTemplate",
                "assetId": row["template_id"],
                "revision": int(row["template_revision"]),
                "contentHash": row["content_hash"],
            },
            "status": row["status"],
            "overlay": row["overlay"],
            "version": int(row["version"]),
        }

    @classmethod
    def _command_hash(cls, request: Any, actor: str) -> str:
        return hashlib.sha256(cls._json({"actor": actor.strip(), "request": request.model_dump(mode="json", by_alias=True)}).encode()).hexdigest()

    @staticmethod
    def _lock(conn: Any, scope: TenantScope, operation: str, key: str) -> None:
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"aip6:{scope.org_id}:{scope.project_id}:{operation}:{key}",))

    @staticmethod
    def _require_replay_hash(row: Any, expected: str) -> None:
        if row["request_hash"] != expected:
            raise AipAgentRegistryConflict("idempotency key was reused with different content")

    @staticmethod
    def _validate_command(scope: TenantScope, key: str, actor: str) -> None:
        if not scope.org_id or not scope.project_id or not key.strip() or not actor.strip():
            raise ValueError("scope, idempotency key and actor are required")
