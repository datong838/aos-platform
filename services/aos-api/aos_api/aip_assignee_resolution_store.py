"""AssigneeResolutionReceipt store and four-kind fail-closed resolver (W-L20)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from aos_api.aip_assignee_resolution import (
    AssigneeResolutionReceipt,
    AssigneeResolutionStatus,
    ResolveAssigneeRequest,
    ToolBindingRecord,
    UpsertToolBindingRequest,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_production_contracts import AssigneeKind
from aos_api.aip_solution_pack_publisher import SOLUTION_PACK_VERSION
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class AipAssigneeResolutionError(RuntimeError):
    code = "AIP_ASSIGNEE_RESOLUTION_FAILED"


class AipAssigneeResolutionBlocked(AipAssigneeResolutionError):
    code = "AIP_ASSIGNEE_RESOLUTION_BLOCKED"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _id(prefix: str, scope: TenantScope, *parts: object) -> str:
    return f"{prefix}-{_hash([scope.org_id, scope.project_id, *parts])[:24]}"


def _tenant(scope: TenantScope) -> TenantContext:
    return TenantContext(org_id=scope.org_id, project_id=scope.project_id)


def assert_publisher_bundle_version_locked() -> str:
    if SOLUTION_PACK_VERSION != "1.3.0":
        raise AipAssigneeResolutionError(
            f"publisher bundleVersion drifted: {SOLUTION_PACK_VERSION}"
        )
    return SOLUTION_PACK_VERSION


class AipAssigneeResolutionStore:
    def upsert_tool_binding(
        self,
        scope: TenantScope,
        request: UpsertToolBindingRequest,
        *,
        now: datetime,
    ) -> ToolBindingRecord:
        with connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_tool_binding(
                  org_id,project_id,binding_id,tool_id,version,agent_instance_id,
                  status,updated_at)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,binding_id) DO UPDATE SET
                    tool_id=EXCLUDED.tool_id,
                    version=EXCLUDED.version,
                    agent_instance_id=EXCLUDED.agent_instance_id,
                    status=EXCLUDED.status,
                    updated_at=EXCLUDED.updated_at""",
                (
                    *scope.key,
                    request.binding_id,
                    request.tool_id,
                    request.version,
                    request.agent_instance_id,
                    request.status,
                    now,
                ),
            )
            conn.commit()
        return ToolBindingRecord(
            tenant=_tenant(scope),
            binding_id=request.binding_id,
            tool_id=request.tool_id,
            version=request.version,
            agent_instance_id=request.agent_instance_id,
            status=request.status,
        )

    def resolve(
        self,
        scope: TenantScope,
        request: ResolveAssigneeRequest,
        actor: str,
        *,
        now: datetime,
    ) -> AssigneeResolutionReceipt:
        assignee = request.assignee
        blockers: list[str] = []
        resolved_ref: str | None = None
        with connect(scope) as conn:
            if assignee.kind is AssigneeKind.HUMAN_PRINCIPAL:
                if not assignee.resource_id.strip():
                    blockers.append("HUMAN_PRINCIPAL_MISSING")
                else:
                    resolved_ref = f"human:{assignee.resource_id}@{assignee.version}"
            elif assignee.kind is AssigneeKind.AGENT_INSTANCE:
                row = conn.execute(
                    """SELECT version FROM aip_agent_instance
                       WHERE org_id=%s AND project_id=%s AND instance_id=%s""",
                    (*scope.key, assignee.resource_id),
                ).fetchone()
                if row is None:
                    blockers.append("AGENT_INSTANCE_MISSING")
                elif int(row["version"]) != assignee.version:
                    blockers.append("AGENT_INSTANCE_DRIFTED")
                else:
                    resolved_ref = f"agent_instance:{assignee.resource_id}@{assignee.version}"
            elif assignee.kind is AssigneeKind.TOOL_BINDING:
                # Fail-closed: exact tenant tool binding + instance scope required.
                # Catalog / global tool registry hits must not resolve.
                row = conn.execute(
                    """SELECT tool_id,version,agent_instance_id,status
                       FROM aip_tool_binding
                       WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                    (*scope.key, assignee.resource_id),
                ).fetchone()
                if row is None:
                    blockers.append("TOOL_BINDING_MISSING")
                elif int(row["version"]) != assignee.version:
                    blockers.append("TOOL_BINDING_DRIFTED")
                elif row["status"] != "active":
                    blockers.append("TOOL_BINDING_DISABLED")
                elif request.require_instance_scope and not row["agent_instance_id"]:
                    blockers.append("TOOL_BINDING_GLOBAL_FORBIDDEN")
                else:
                    resolved_ref = (
                        f"tool_binding:{assignee.resource_id}@{assignee.version}"
                        f"→{row['agent_instance_id']}/{row['tool_id']}"
                    )
            elif assignee.kind is AssigneeKind.PROVIDER_CAPABILITY_BINDING:
                row = conn.execute(
                    """SELECT version,status,operational_readiness
                       FROM aip_capability_binding
                       WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                    (*scope.key, assignee.resource_id),
                ).fetchone()
                if row is None:
                    blockers.append("PROVIDER_BINDING_MISSING")
                elif int(row["version"]) != assignee.version:
                    blockers.append("PROVIDER_BINDING_DRIFTED")
                elif row["status"] != "active":
                    blockers.append("PROVIDER_BINDING_NOT_ACTIVE")
                else:
                    readiness = row["operational_readiness"]
                    if isinstance(readiness, dict):
                        readiness = readiness.get("readiness") or readiness.get("status")
                    if str(readiness) != "available":
                        blockers.append("PROVIDER_BINDING_NOT_OPERATIONAL")
                    else:
                        resolved_ref = (
                            f"provider_capability_binding:{assignee.resource_id}"
                            f"@{assignee.version}"
                        )
            else:
                blockers.append("ASSIGNEE_KIND_UNSUPPORTED")

            status = (
                AssigneeResolutionStatus.RESOLVED
                if not blockers
                else AssigneeResolutionStatus.BLOCKED
            )
            payload = {
                "subjectId": request.subject_id,
                "kind": assignee.kind.value,
                "resourceId": assignee.resource_id,
                "version": assignee.version,
                "status": status.value,
                "resolvedRef": resolved_ref,
                "blockerCodes": blockers,
                "bundleVersionLock": assert_publisher_bundle_version_locked(),
            }
            content_hash = _hash(payload)
            receipt_id = _id(
                "assignee-res",
                scope,
                request.subject_id,
                assignee.kind.value,
                assignee.resource_id,
                assignee.version,
                content_hash,
            )
            conn.execute(
                """INSERT INTO aip_assignee_resolution_receipt(
                  org_id,project_id,receipt_id,subject_id,kind,resource_id,version,
                  status,resolved_ref,blocker_codes,actor,content_hash,created_at)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,receipt_id) DO NOTHING""",
                (
                    *scope.key,
                    receipt_id,
                    request.subject_id,
                    assignee.kind.value,
                    assignee.resource_id,
                    assignee.version,
                    status.value,
                    resolved_ref,
                    _json(blockers),
                    actor,
                    content_hash,
                    now,
                ),
            )
            row = conn.execute(
                """SELECT * FROM aip_assignee_resolution_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, receipt_id),
            ).fetchone()
            conn.commit()
            return self._receipt(scope, row)

    def _receipt(self, scope: TenantScope, row: Any) -> AssigneeResolutionReceipt:
        blockers = row["blocker_codes"]
        if isinstance(blockers, str):
            blockers = json.loads(blockers)
        return AssigneeResolutionReceipt(
            tenant=_tenant(scope),
            receipt_id=row["receipt_id"],
            subject_id=row["subject_id"],
            kind=AssigneeKind(row["kind"]),
            resource_id=row["resource_id"],
            version=row["version"],
            status=AssigneeResolutionStatus(row["status"]),
            resolved_ref=row["resolved_ref"],
            blocker_codes=list(blockers),
            actor=row["actor"],
            created_at=row["created_at"],
            content_hash=row["content_hash"],
        )


__all__ = [
    "AipAssigneeResolutionBlocked",
    "AipAssigneeResolutionError",
    "AipAssigneeResolutionStore",
    "assert_publisher_bundle_version_locked",
]
