"""PostgreSQL authority for exact-publication Logic automation policies."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.aip_logic_automation_models import (
    CreateLogicAutomationRequest,
    LogicAutomationPolicy,
    LogicAutomationRun,
    UpdateLogicAutomationRequest,
)
from aos_api.db import connect as db_connect
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[[], AbstractContextManager[Any]]
log = get_logger("aos-api.logic-automation-store")


class LogicAutomationError(RuntimeError):
    code = "LOGIC_AUTOMATION_ERROR"


class LogicAutomationNotFound(LogicAutomationError):
    code = "LOGIC_AUTOMATION_NOT_FOUND"


class LogicAutomationConflict(LogicAutomationError):
    code = "LOGIC_AUTOMATION_VERSION_CONFLICT"


class LogicAutomationGateRejected(LogicAutomationError):
    code = "LOGIC_AUTOMATION_GATE_REJECTED"


class LogicAutomationPersistenceError(LogicAutomationError):
    code = "LOGIC_AUTOMATION_PERSISTENCE_ERROR"


class LogicAutomationStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def list(self, org_id: str, project_id: str, graph_id: str) -> list[LogicAutomationPolicy]:
        try:
            with self._connect(org_id, project_id) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_logic_automation_policy
                       WHERE org_id=%s AND project_id=%s AND graph_id=%s
                       ORDER BY updated_at DESC,automation_id DESC""",
                    (org_id, project_id, graph_id),
                ).fetchall()
            return [self._policy(row) for row in rows]
        except Exception as exc:
            log.exception("logic_automation_list_failed error_type=%s", type(exc).__name__)
            raise LogicAutomationPersistenceError("failed to list automation policies") from exc

    def list_all(self, org_id: str, project_id: str) -> list[LogicAutomationPolicy]:
        """List the current tenant's persisted policies for cross-graph evidence views."""
        try:
            with self._connect(org_id, project_id) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_logic_automation_policy
                       WHERE org_id=%s AND project_id=%s
                       ORDER BY updated_at DESC,automation_id DESC""",
                    (org_id, project_id),
                ).fetchall()
            return [self._policy(row) for row in rows]
        except Exception as exc:
            log.exception("logic_automation_list_all_failed error_type=%s", type(exc).__name__)
            raise LogicAutomationPersistenceError("failed to list tenant automation policies") from exc

    def get(self, org_id: str, project_id: str, graph_id: str, automation_id: str) -> LogicAutomationPolicy:
        try:
            with self._connect(org_id, project_id) as conn:
                row = conn.execute(
                    """SELECT * FROM aip_logic_automation_policy
                       WHERE org_id=%s AND project_id=%s AND graph_id=%s AND automation_id=%s""",
                    (org_id, project_id, graph_id, automation_id),
                ).fetchone()
            if row is None:
                raise LogicAutomationNotFound("logic automation policy not found")
            return self._policy(row)
        except LogicAutomationError:
            raise
        except Exception as exc:
            raise LogicAutomationPersistenceError("failed to read automation policy") from exc

    def create(
        self,
        org_id: str,
        project_id: str,
        graph_id: str,
        actor: str,
        body: CreateLogicAutomationRequest,
    ) -> LogicAutomationPolicy:
        automation_id = f"logic-auto-{uuid.uuid4().hex}"
        try:
            with self._connect(org_id, project_id) as conn:
                publication = conn.execute(
                    """SELECT graph_revision,graph_hash FROM aip_logic_publication
                       WHERE org_id=%s AND project_id=%s AND graph_id=%s AND publication_id=%s""",
                    (org_id, project_id, graph_id, body.publication_id),
                ).fetchone()
                if publication is None:
                    raise LogicAutomationGateRejected(
                        "automation requires an immutable publication owned by the current tenant"
                    )
                row = conn.execute(
                    """INSERT INTO aip_logic_automation_policy (
                         org_id,project_id,automation_id,graph_id,publication_id,
                         graph_revision,graph_hash,name,trigger_type,schedule,status,
                         revision,actor,created_at,updated_at
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',1,%s,NOW(),NOW())
                       RETURNING *""",
                    (
                        org_id, project_id, automation_id, graph_id, body.publication_id,
                        int(publication["graph_revision"]), str(publication["graph_hash"]),
                        body.name, body.trigger_type, body.schedule.strip(), actor,
                    ),
                ).fetchone()
                conn.commit()
            return self._policy(row)
        except LogicAutomationError:
            raise
        except Exception as exc:
            log.exception("logic_automation_create_failed error_type=%s", type(exc).__name__)
            raise LogicAutomationPersistenceError("failed to create automation policy") from exc

    def update(
        self,
        org_id: str,
        project_id: str,
        graph_id: str,
        automation_id: str,
        actor: str,
        body: UpdateLogicAutomationRequest,
    ) -> LogicAutomationPolicy:
        updates = body.model_dump(exclude={"expected_revision"}, exclude_none=True)
        if not updates:
            return self.get(org_id, project_id, graph_id, automation_id)
        current = self.get(org_id, project_id, graph_id, automation_id)
        merged = CreateLogicAutomationRequest(
            publication_id=current.publication_id,
            name=str(updates.get("name", current.name)),
            trigger_type=updates.get("trigger_type", current.trigger_type),
            schedule=str(updates.get("schedule", current.schedule)),
        )
        updates["name"] = merged.name
        updates["trigger_type"] = merged.trigger_type
        updates["schedule"] = merged.schedule
        allowed = {"name", "trigger_type", "schedule", "status"}
        assignments = [f"{key}=%s" for key in updates if key in allowed]
        values = [str(updates[key]).strip() for key in updates if key in allowed]
        try:
            with self._connect(org_id, project_id) as conn:
                row = conn.execute(
                    f"""UPDATE aip_logic_automation_policy SET {','.join(assignments)},
                           revision=revision+1,actor=%s,updated_at=NOW()
                         WHERE org_id=%s AND project_id=%s AND graph_id=%s
                           AND automation_id=%s AND revision=%s RETURNING *""",
                    (*values, actor, org_id, project_id, graph_id, automation_id, body.expected_revision),
                ).fetchone()
                if row is None:
                    exists = conn.execute(
                        """SELECT revision FROM aip_logic_automation_policy
                           WHERE org_id=%s AND project_id=%s AND graph_id=%s AND automation_id=%s""",
                        (org_id, project_id, graph_id, automation_id),
                    ).fetchone()
                    if exists is None:
                        raise LogicAutomationNotFound("logic automation policy not found")
                    raise LogicAutomationConflict("automation policy revision changed")
                conn.commit()
            return self._policy(row)
        except LogicAutomationError:
            raise
        except Exception as exc:
            raise LogicAutomationPersistenceError("failed to update automation policy") from exc

    def record_run(
        self,
        org_id: str,
        project_id: str,
        policy: LogicAutomationPolicy,
        *,
        idempotency_key: str,
        task_id: str,
        task_run_id: str,
        status: str = "accepted",
        trigger: str = "manual",
    ) -> LogicAutomationRun:
        run_id = f"logic-auto-run-{uuid.uuid4().hex}"
        receipt_id = f"logic-auto-receipt-{uuid.uuid4().hex}"
        try:
            with self._connect(org_id, project_id) as conn:
                row = conn.execute(
                    """INSERT INTO aip_logic_automation_run (
                         org_id,project_id,run_id,automation_id,policy_revision,trigger,
                         idempotency_key,task_id,task_run_id,status,receipt_id,
                         production_written,created_at,finished_at
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,FALSE,NOW(),NOW())
                       ON CONFLICT (org_id,project_id,automation_id,idempotency_key)
                       DO NOTHING
                       RETURNING *""",
                    (
                        org_id, project_id, run_id, policy.automation_id,
                        policy.revision, trigger, idempotency_key, task_id, task_run_id, status, receipt_id,
                    ),
                ).fetchone()
                if row is None:
                    row = conn.execute(
                        """SELECT * FROM aip_logic_automation_run
                           WHERE org_id=%s AND project_id=%s AND automation_id=%s
                             AND idempotency_key=%s""",
                        (org_id, project_id, policy.automation_id, idempotency_key),
                    ).fetchone()
                conn.commit()
            return self._run(row)
        except Exception as exc:
            log.exception("logic_automation_record_run_failed error_type=%s", type(exc).__name__)
            raise LogicAutomationPersistenceError("failed to record automation run") from exc

    def list_active_cron_targets(self) -> list[tuple[str, str, LogicAutomationPolicy]]:
        """Global scheduler discovery; every subsequent read/write is rebound to the row tenant."""
        try:
            with self._connect_factory() as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_logic_automation_policy
                       WHERE status='active' AND trigger_type='cron'
                       ORDER BY org_id,project_id,automation_id"""
                ).fetchall()
            return [(str(row["org_id"]), str(row["project_id"]), self._policy(row)) for row in rows]
        except Exception as exc:
            raise LogicAutomationPersistenceError("failed to discover active cron policies") from exc

    def list_runs(
        self, org_id: str, project_id: str, graph_id: str, automation_id: str
    ) -> list[LogicAutomationRun]:
        self.get(org_id, project_id, graph_id, automation_id)
        try:
            with self._connect(org_id, project_id) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_logic_automation_run
                       WHERE org_id=%s AND project_id=%s AND automation_id=%s
                       ORDER BY created_at DESC,run_id DESC LIMIT 100""",
                    (org_id, project_id, automation_id),
                ).fetchall()
            return [self._run(row) for row in rows]
        except Exception as exc:
            raise LogicAutomationPersistenceError("failed to list automation runs") from exc

    def _connect(self, org_id: str, project_id: str):
        if not org_id.strip() or not project_id.strip():
            raise ValueError("tenant scope is required")
        return self._connect_factory(TenantScope(org_id=org_id, project_id=project_id))

    @staticmethod
    def _policy(row: Any) -> LogicAutomationPolicy:
        payload = dict(row)
        payload.pop("org_id", None)
        payload.pop("project_id", None)
        return LogicAutomationPolicy(**payload)

    @staticmethod
    def _run(row: Any) -> LogicAutomationRun:
        payload = dict(row)
        payload.pop("org_id", None)
        payload.pop("project_id", None)
        payload.pop("idempotency_key", None)
        return LogicAutomationRun(**payload)
