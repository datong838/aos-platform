"""Canonical Assist context assembly boundary for AIP-8 P8-4A."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Protocol

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_assist_contracts import (
    AssistAuthorityContext,
    AssistContextSnapshot,
    AssistSubjectRefs,
)
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import ModelRuntimeStoreError
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class AssistContextBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AssistAuthorityReader(Protocol):
    def resolve(
        self,
        scope: TenantScope,
        subject: AssistSubjectRefs,
    ) -> AssistAuthorityContext: ...


class AipAssistContextAssembler:
    def __init__(self, reader: AssistAuthorityReader) -> None:
        self._reader = reader

    def assemble(
        self,
        scope: TenantScope,
        subject: AssistSubjectRefs,
        *,
        principal_markings: list[str],
    ) -> AssistContextSnapshot:
        authority = self._reader.resolve(scope, subject)
        if (authority.tenant.org_id, authority.tenant.project_id) != scope.key:
            raise AssistContextBlocked("ASSIST_CONTEXT_TENANT_DRIFT")
        if (
            authority.task_ref != subject.task_ref
            or authority.task_run_ref != subject.task_run_ref
            or authority.agent_run_ref != subject.agent_run_ref
            or authority.selection_refs != subject.selection_refs
            or authority.cutoff_at != subject.cutoff_at
        ):
            raise AssistContextBlocked("ASSIST_CONTEXT_EXACT_REF_DRIFT")
        if not set(authority.markings).issubset(set(principal_markings)):
            raise AssistContextBlocked("ASSIST_CONTEXT_MARKING_DENIED")
        if authority.readiness_blockers:
            raise AssistContextBlocked(authority.readiness_blockers[0].code)

        payload = authority.model_dump(mode="json", by_alias=True)
        context_hash = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return AssistContextSnapshot(**authority.model_dump(), context_hash=context_hash)


def _asset_ref(value: object, authority: str) -> ResourceRef:
    ref = VersionedAssetRef.model_validate(value)
    return ResourceRef(
        resource_type=ref.asset_type,
        resource_id=ref.asset_id,
        revision=str(ref.revision),
        authority=f"{authority}:{ref.content_hash}",
    )


class PostgresAssistAuthorityReader:
    """Resolve ref-only Assist context from canonical AIP authorities."""

    def __init__(self, *, model_resolver: AipModelRuntimeResolver | None = None) -> None:
        self._model_resolver = model_resolver or AipModelRuntimeResolver()

    def resolve(
        self,
        scope: TenantScope,
        subject: AssistSubjectRefs,
    ) -> AssistAuthorityContext:
        with connect(scope) as conn:
            row = conn.execute(
                """SELECT ar.*,tr.version AS task_run_version,
                  tr.status AS task_run_status,t.version AS task_version,
                  p.revision AS plan_revision,p.content_hash AS plan_hash,
                  ai.status AS instance_status,
                  sb.status AS binding_status,sb.version AS binding_version,
                  sb.capability_refs,sb.readiness AS binding_readiness,
                  sb.readiness_expires_at,sb.eval_gate_ref
                FROM aip_agent_run ar
                JOIN aip_task t ON t.org_id=ar.org_id AND t.project_id=ar.project_id
                  AND t.task_id=ar.task_id
                JOIN aip_task_run tr ON tr.org_id=ar.org_id AND tr.project_id=ar.project_id
                  AND tr.run_id=ar.task_run_id
                JOIN aip_plan_revision p ON p.org_id=ar.org_id AND p.project_id=ar.project_id
                  AND p.plan_revision_id=tr.plan_revision_id
                JOIN aip_agent_instance ai ON ai.org_id=ar.org_id AND ai.project_id=ar.project_id
                  AND ai.instance_id=ar.instance_id
                JOIN aip_skill_binding sb ON sb.org_id=ar.org_id AND sb.project_id=ar.project_id
                  AND sb.binding_id=ar.skill_binding_id
                WHERE ar.org_id=%s AND ar.project_id=%s AND ar.agent_run_id=%s""",
                (*scope.key, subject.agent_run_ref.resource_id),
            ).fetchone()
            if row is None:
                raise AssistContextBlocked("ASSIST_AGENT_RUN_NOT_FOUND")

            exact_task = ResourceRef.model_validate(row["task_ref"])
            exact_task_run = ResourceRef.model_validate(row["task_run_ref"])
            exact_agent_run = ResourceRef(
                resource_type="AgentRun",
                resource_id=row["agent_run_id"],
                revision=str(row["version"]),
                authority="aip-agent-registry",
            )
            if (
                exact_task != subject.task_ref
                or exact_task_run != subject.task_run_ref
                or exact_agent_run != subject.agent_run_ref
            ):
                raise AssistContextBlocked("ASSIST_CONTEXT_EXACT_REF_DRIFT")
            if row["status"] != "running" or row["task_run_status"] != "running":
                raise AssistContextBlocked("ASSIST_AGENT_RUN_NOT_RUNNING")
            if row["instance_status"] != "active":
                raise AssistContextBlocked("ASSIST_AGENT_INSTANCE_NOT_ACTIVE")
            now = datetime.now(UTC)
            if (
                row["binding_status"] != "active"
                or row["binding_readiness"] != "ready"
                or row["readiness_expires_at"] is None
                or row["readiness_expires_at"] <= now
            ):
                raise AssistContextBlocked("ASSIST_SKILL_BINDING_NOT_READY")

            input_refs = [ResourceRef.model_validate(value) for value in row["input_refs"]]
            selections = [
                value for value in input_refs if value.resource_type == "SelectionRevision"
            ]
            if selections != subject.selection_refs:
                raise AssistContextBlocked("ASSIST_SELECTION_EXACT_REF_DRIFT")
            knowledge_refs = [
                value for value in input_refs if value.resource_type == "KnowledgeCitation"
            ]

            capability_ids = list(row["capability_refs"] or [])
            capability_refs: list[ResourceRef] = []
            if capability_ids:
                capabilities = conn.execute(
                    """SELECT binding_id,version,status,health,operational_readiness,
                      readiness_expires_at FROM aip_capability_binding
                    WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)""",
                    (*scope.key, capability_ids),
                ).fetchall()
                if {item["binding_id"] for item in capabilities} != set(capability_ids):
                    raise AssistContextBlocked("ASSIST_CAPABILITY_BINDING_NOT_FOUND")
                by_id = {item["binding_id"]: item for item in capabilities}
                for binding_id in capability_ids:
                    item = by_id[binding_id]
                    if (
                        item["status"] != "active"
                        or item["health"] != "healthy"
                        or item["operational_readiness"] != "ready"
                        or item["readiness_expires_at"] is None
                        or item["readiness_expires_at"] <= now
                    ):
                        raise AssistContextBlocked("ASSIST_CAPABILITY_BINDING_NOT_READY")
                    capability_refs.append(
                        ResourceRef(
                            resource_type="CapabilityBinding",
                            resource_id=binding_id,
                            revision=str(item["version"]),
                            authority="aip-capability-binding",
                        )
                    )

        route = VersionedAssetRef.model_validate(row["model_route_ref"])
        policy = VersionedAssetRef.model_validate(row["policy_ref"])
        try:
            resolution = self._model_resolver.resolve(scope, route.asset_id, now=now)
        except ModelRuntimeStoreError as exc:
            raise AssistContextBlocked("ASSIST_MODEL_RUNTIME_UNAVAILABLE") from exc
        if resolution.readiness is not ModelRuntimeReadiness.READY:
            code = resolution.blocker_codes[0] if resolution.blocker_codes else "not_ready"
            raise AssistContextBlocked(f"ASSIST_MODEL_RUNTIME_{code}".upper())
        if resolution.route != route or resolution.policy != policy:
            raise AssistContextBlocked("ASSIST_MODEL_RUNTIME_EXACT_REF_DRIFT")

        return AssistAuthorityContext(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            task_ref=exact_task,
            task_run_ref=exact_task_run,
            plan_ref=ResourceRef.model_validate(row["plan_ref"]),
            agent_run_ref=exact_agent_run,
            agent_instance_ref=_asset_ref(row["instance_ref"], "aip-agent-registry"),
            skill_ref=_asset_ref(row["skill_ref"], "aip-agent-registry"),
            logic_ref=_asset_ref(row["logic_ref"], "aip-logic"),
            model_route_ref=_asset_ref(row["model_route_ref"], "aip-model-runtime"),
            policy_ref=_asset_ref(row["policy_ref"], "aip-model-runtime"),
            eval_ref=_asset_ref(row["eval_gate_ref"], "aip-eval"),
            skill_binding_ref=ResourceRef(
                resource_type="SkillBinding",
                resource_id=row["skill_binding_id"],
                revision=str(row["binding_version"]),
                authority="aip-agent-registry",
            ),
            capability_binding_refs=capability_refs,
            selection_refs=selections,
            knowledge_citation_refs=knowledge_refs,
            markings=["public"],
            cutoff_at=subject.cutoff_at,
        )


__all__ = [
    "AipAssistContextAssembler",
    "AssistAuthorityReader",
    "AssistContextBlocked",
    "PostgresAssistAuthorityReader",
]
