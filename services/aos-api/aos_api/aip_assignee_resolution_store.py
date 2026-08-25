"""AssigneeResolutionReceipt store and four-kind fail-closed resolver (W-L20)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from aos_api.aip_assignee_resolution import (
    AssigneeCandidateDecision,
    AssigneeResolutionReceipt,
    AssigneeResolutionStatus,
    ResolveAssigneeRequest,
    ToolBindingRecord,
    UpsertToolBindingRequest,
)
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef
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
    def __init__(
        self,
        connect_factory: Callable[[TenantScope], Any] = connect,
        membership_resolver: Callable[[str, str, str], bool] | None = None,
    ) -> None:
        self._connect = connect_factory
        self._membership_resolver = membership_resolver

    def upsert_tool_binding(
        self,
        scope: TenantScope,
        request: UpsertToolBindingRequest,
        *,
        now: datetime,
    ) -> ToolBindingRecord:
        with self._connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_tool_binding(
                  org_id,project_id,binding_id,tool_id,version,agent_instance_id,
                  status,capability_binding_ids,policy_refs,updated_at)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                  ON CONFLICT (org_id,project_id,binding_id) DO UPDATE SET
                    tool_id=EXCLUDED.tool_id,
                    version=EXCLUDED.version,
                    agent_instance_id=EXCLUDED.agent_instance_id,
                    status=EXCLUDED.status,
                    capability_binding_ids=EXCLUDED.capability_binding_ids,
                    policy_refs=EXCLUDED.policy_refs,
                    updated_at=EXCLUDED.updated_at""",
                (
                    *scope.key,
                    request.binding_id,
                    request.tool_id,
                    request.version,
                    request.agent_instance_id,
                    request.status,
                    _json(request.capability_binding_ids),
                    _json(
                        [item.model_dump(mode="json", by_alias=True) for item in request.policy_refs]
                    ),
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
            capability_binding_ids=request.capability_binding_ids,
            policy_refs=request.policy_refs,
        )

    def resolve(
        self,
        scope: TenantScope,
        request: ResolveAssigneeRequest,
        actor: str,
        *,
        now: datetime,
    ) -> AssigneeResolutionReceipt:
        with self._connect(scope) as conn:
            decisions = [
                self._evaluate_candidate(conn, scope, request, candidate, now)
                for candidate in request.canonical_candidates
            ]
            selected = next(
                (item for item in decisions if item.status is AssigneeResolutionStatus.RESOLVED),
                None,
            )
            status = (
                AssigneeResolutionStatus.RESOLVED
                if selected is not None
                else AssigneeResolutionStatus.BLOCKED
            )
            representative = selected.assignee if selected else request.canonical_candidates[0]
            blockers = (
                []
                if selected is not None
                else sorted({code for item in decisions for code in item.blocker_codes})
            )
            binding_refs = selected.binding_refs if selected else []
            snapshot_payload = {
                "subjectId": request.subject_id,
                "requiredCapabilities": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in request.required_capabilities
                ],
                "candidates": [
                    item.model_dump(mode="json", by_alias=True) for item in decisions
                ],
                "selectedAssignee": (
                    representative.model_dump(mode="json", by_alias=True)
                    if selected is not None
                    else None
                ),
                "policyRefs": [
                    item.model_dump(mode="json", by_alias=True) for item in request.policy_refs
                ],
                "bundleVersionLock": assert_publisher_bundle_version_locked(),
            }
            snapshot_hash = _hash(snapshot_payload)
            expires_at = now + timedelta(seconds=request.freshness_seconds)
            payload = {
                **snapshot_payload,
                "kind": representative.kind.value,
                "resourceId": representative.resource_id,
                "version": representative.version,
                "status": status.value,
                "resolvedRef": selected.resolved_ref if selected else None,
                "blockerCodes": blockers,
                "bindingRefs": [
                    item.model_dump(mode="json", by_alias=True) for item in binding_refs
                ],
                "snapshotHash": snapshot_hash,
            }
            content_hash = _hash(payload)
            receipt_id = _id(
                "assignee-res",
                scope,
                request.subject_id,
                snapshot_hash,
            )
            conn.execute(
                """INSERT INTO aip_assignee_resolution_receipt(
                  org_id,project_id,receipt_id,subject_id,kind,resource_id,version,
                  status,resolved_ref,blocker_codes,actor,content_hash,created_at,
                  selected_assignee,required_capability_refs,candidate_decisions,
                  binding_refs,policy_refs,snapshot_hash,expires_at)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,
                         %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)
                  ON CONFLICT (org_id,project_id,receipt_id) DO NOTHING""",
                (
                    *scope.key,
                    receipt_id,
                    request.subject_id,
                    representative.kind.value,
                    representative.resource_id,
                    representative.version,
                    status.value,
                    selected.resolved_ref if selected else None,
                    _json(blockers),
                    actor,
                    content_hash,
                    now,
                    (
                        _json(representative.model_dump(mode="json", by_alias=True))
                        if selected is not None
                        else None
                    ),
                    _json(
                        [item.model_dump(mode="json", by_alias=True) for item in request.required_capabilities]
                    ),
                    _json([item.model_dump(mode="json", by_alias=True) for item in decisions]),
                    _json([item.model_dump(mode="json", by_alias=True) for item in binding_refs]),
                    _json([item.model_dump(mode="json", by_alias=True) for item in request.policy_refs]),
                    snapshot_hash,
                    expires_at,
                ),
            )
            row = conn.execute(
                """SELECT * FROM aip_assignee_resolution_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, receipt_id),
            ).fetchone()
            conn.commit()
            return self._receipt(scope, row)

    def _evaluate_candidate(
        self,
        conn: Any,
        scope: TenantScope,
        request: ResolveAssigneeRequest,
        assignee: AssigneeRef,
        now: datetime,
    ) -> AssigneeCandidateDecision:
        blockers: list[str] = []
        resolved_ref: str | None = None
        binding_refs: list[VersionedAssetRef] = []
        if assignee.kind is AssigneeKind.HUMAN_PRINCIPAL:
            membership_exists = (
                self._membership_resolver(
                    scope.org_id, scope.project_id, assignee.resource_id
                )
                if self._membership_resolver is not None
                else conn.execute(
                    """SELECT 1 FROM meta_membership
                        WHERE org_id=%s AND project_id=%s AND subject=%s""",
                    (*scope.key, assignee.resource_id),
                ).fetchone()
                is not None
            )
            if assignee.version != 1 or not membership_exists:
                blockers.append("HUMAN_PRINCIPAL_NOT_TENANT_MEMBER")
            elif request.required_capabilities:
                blockers.append("HUMAN_CAPABILITY_BINDING_MISSING")
            else:
                resolved_ref = f"human:{assignee.resource_id}@{assignee.version}"
        elif assignee.kind is AssigneeKind.AGENT_INSTANCE:
            row = conn.execute(
                """SELECT instance.template_id,instance.template_revision,instance.status,
                          instance.version,template.content_hash,template.lifecycle
                     FROM aip_agent_instance AS instance
                     JOIN aip_agent_template_revision AS template
                       ON template.template_id=instance.template_id
                      AND template.revision=instance.template_revision
                    WHERE instance.org_id=%s AND instance.project_id=%s
                      AND instance.instance_id=%s""",
                (*scope.key, assignee.resource_id),
            ).fetchone()
            if row is None:
                blockers.append("AGENT_INSTANCE_MISSING")
            elif int(row["version"]) != assignee.version:
                blockers.append("AGENT_INSTANCE_DRIFTED")
            elif row["status"] != "active" or row["lifecycle"] != "published":
                blockers.append("AGENT_INSTANCE_NOT_ACTIVE")
            else:
                binding_refs.append(
                    VersionedAssetRef(
                        asset_type="AgentTemplate",
                        asset_id=row["template_id"],
                        revision=int(row["template_revision"]),
                        content_hash=row["content_hash"],
                    )
                )
                skill_rows = conn.execute(
                    """SELECT binding_id,version,capability_refs,budget_policy_ref,
                              readiness,dependency_snapshot_hash,readiness_expires_at
                         FROM aip_skill_binding
                        WHERE org_id=%s AND project_id=%s AND instance_id=%s
                          AND status='active'
                        ORDER BY binding_id ASC""",
                    (*scope.key, assignee.resource_id),
                ).fetchall()
                if not skill_rows:
                    blockers.append("SKILL_BINDING_NOT_ACTIVE")
                else:
                    capability_ids: list[str] = []
                    operational_skill_count = 0
                    for skill in skill_rows:
                        if (
                            skill["readiness"] not in {"available", "degraded"}
                            or not skill["dependency_snapshot_hash"]
                            or not skill["readiness_expires_at"]
                            or skill["readiness_expires_at"] <= now
                        ):
                            continue
                        operational_skill_count += 1
                        capability_ids.extend(self._binding_ids(skill["capability_refs"]))
                        binding_refs.append(
                            self._snapshot_ref(
                                "SkillBinding",
                                skill["binding_id"],
                                int(skill["version"]),
                                {
                                    "capabilityRefs": self._load(skill["capability_refs"]),
                                    "budgetPolicyRef": self._load(skill["budget_policy_ref"]),
                                    "dependencySnapshotHash": skill["dependency_snapshot_hash"],
                                },
                            )
                        )
                    if operational_skill_count == 0:
                        blockers.append("SKILL_BINDING_NOT_OPERATIONAL")
                    cap_blockers, cap_refs = self._evaluate_capability_bindings(
                        conn, scope, capability_ids, request.required_capabilities, now
                    )
                    blockers.extend(cap_blockers)
                    binding_refs.extend(cap_refs)
                if not blockers:
                    resolved_ref = (
                        f"agent_instance:{assignee.resource_id}@{assignee.version}"
                    )
        elif assignee.kind is AssigneeKind.TOOL_BINDING:
            row = conn.execute(
                """SELECT tool_id,version,agent_instance_id,status,
                          capability_binding_ids,policy_refs
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
                instance = conn.execute(
                    """SELECT status FROM aip_agent_instance
                        WHERE org_id=%s AND project_id=%s AND instance_id=%s""",
                    (*scope.key, row["agent_instance_id"]),
                ).fetchone()
                if instance is None or instance["status"] != "active":
                    blockers.append("TOOL_BINDING_INSTANCE_NOT_ACTIVE")
                cap_blockers, cap_refs = self._evaluate_capability_bindings(
                    conn,
                    scope,
                    self._binding_ids(row["capability_binding_ids"]),
                    request.required_capabilities,
                    now,
                )
                blockers.extend(cap_blockers)
                binding_refs.extend(cap_refs)
                binding_refs.append(
                    self._snapshot_ref(
                        "ToolBinding",
                        assignee.resource_id,
                        assignee.version,
                        {
                            "toolId": row["tool_id"],
                            "agentInstanceId": row["agent_instance_id"],
                            "capabilityBindingIds": self._load(row["capability_binding_ids"]),
                            "policyRefs": self._load(row["policy_refs"]),
                        },
                    )
                )
                if not blockers:
                    resolved_ref = (
                        f"tool_binding:{assignee.resource_id}@{assignee.version}"
                        f"→{row['agent_instance_id']}/{row['tool_id']}"
                    )
        elif assignee.kind is AssigneeKind.PROVIDER_CAPABILITY_BINDING:
            cap_blockers, cap_refs = self._evaluate_capability_bindings(
                conn,
                scope,
                [assignee.resource_id],
                request.required_capabilities,
                now,
                expected_version=assignee.version,
            )
            blockers.extend(cap_blockers)
            binding_refs.extend(cap_refs)
            if not blockers:
                resolved_ref = (
                    f"provider_capability_binding:{assignee.resource_id}"
                    f"@{assignee.version}"
                )
        else:
            blockers.append("ASSIGNEE_KIND_UNSUPPORTED")
        return AssigneeCandidateDecision(
            assignee=assignee,
            status=(
                AssigneeResolutionStatus.BLOCKED
                if blockers
                else AssigneeResolutionStatus.RESOLVED
            ),
            blocker_codes=sorted(set(blockers)),
            resolved_ref=resolved_ref,
            binding_refs=sorted(
                binding_refs,
                key=lambda item: (item.asset_type, item.asset_id, item.revision),
            ),
        )

    def _evaluate_capability_bindings(
        self,
        conn: Any,
        scope: TenantScope,
        binding_ids: list[str],
        required: list[VersionedAssetRef],
        now: datetime,
        *,
        expected_version: int | None = None,
    ) -> tuple[list[str], list[VersionedAssetRef]]:
        if not binding_ids:
            return (
                (["CAPABILITY_BINDING_MISSING"] if required else []),
                [],
            )
        rows = conn.execute(
            """SELECT binding_id,version,capability_ref,status,health,
                      operational_readiness,allow_degraded,dependency_snapshot_hash,
                      readiness_expires_at,network_policy_revision,quota_policy_revision
                 FROM aip_capability_binding
                WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)
                ORDER BY binding_id ASC""",
            (*scope.key, sorted(set(binding_ids))),
        ).fetchall()
        blockers: list[str] = []
        refs: list[VersionedAssetRef] = []
        provided: set[tuple[str, str, int, str]] = set()
        if len(rows) != len(set(binding_ids)):
            blockers.append("CAPABILITY_BINDING_MISSING")
        for row in rows:
            if expected_version is not None and int(row["version"]) != expected_version:
                blockers.append("PROVIDER_BINDING_DRIFTED")
                continue
            if row["status"] != "active" or row["health"] != "healthy":
                blockers.append("CAPABILITY_BINDING_NOT_ACTIVE")
                continue
            usable = row["operational_readiness"] == "available" or (
                row["operational_readiness"] == "degraded" and bool(row["allow_degraded"])
            )
            if not usable:
                blockers.append("CAPABILITY_BINDING_NOT_OPERATIONAL")
                continue
            if (
                not row["dependency_snapshot_hash"]
                or not row["readiness_expires_at"]
                or row["readiness_expires_at"] <= now
            ):
                blockers.append("CAPABILITY_BINDING_STALE")
                continue
            try:
                capability = VersionedAssetRef.model_validate(
                    self._load(row["capability_ref"])
                )
            except (TypeError, ValueError):
                blockers.append("CAPABILITY_REF_INVALID")
                continue
            provided.add(
                (
                    capability.asset_type,
                    capability.asset_id,
                    capability.revision,
                    capability.content_hash,
                )
            )
            refs.append(
                self._snapshot_ref(
                    "CapabilityBinding",
                    row["binding_id"],
                    int(row["version"]),
                    {
                        "capability": capability.model_dump(mode="json", by_alias=True),
                        "dependencySnapshotHash": row["dependency_snapshot_hash"],
                        "networkPolicyRevision": row["network_policy_revision"],
                        "quotaPolicyRevision": row["quota_policy_revision"],
                    },
                )
            )
        expected = {
            (item.asset_type, item.asset_id, item.revision, item.content_hash)
            for item in required
        }
        if not expected <= provided:
            blockers.append("REQUIRED_CAPABILITY_NOT_EXACTLY_COVERED")
        return sorted(set(blockers)), refs

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @classmethod
    def _binding_ids(cls, value: Any) -> list[str]:
        loaded = cls._load(value) or []
        result: list[str] = []
        for item in loaded:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, dict):
                identifier = item.get("bindingId") or item.get("resourceId")
                if isinstance(identifier, str) and identifier.strip():
                    result.append(identifier.strip())
        return sorted(set(result))

    @staticmethod
    def _snapshot_ref(
        asset_type: str, asset_id: str, revision: int, payload: object
    ) -> VersionedAssetRef:
        return VersionedAssetRef(
            asset_type=asset_type,
            asset_id=asset_id,
            revision=revision,
            content_hash=_hash(payload),
        )

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
            selected_assignee=self._load(row.get("selected_assignee")),
            required_capabilities=self._load(row.get("required_capability_refs")) or [],
            candidate_decisions=self._load(row.get("candidate_decisions")) or [],
            binding_refs=self._load(row.get("binding_refs")) or [],
            policy_refs=self._load(row.get("policy_refs")) or [],
            snapshot_hash=row.get("snapshot_hash"),
            expires_at=row.get("expires_at"),
        )


__all__ = [
    "AipAssigneeResolutionBlocked",
    "AipAssigneeResolutionError",
    "AipAssigneeResolutionStore",
    "assert_publisher_bundle_version_locked",
]
