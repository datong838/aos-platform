"""Unique compile-only bridge from Workshop modules to canonical AIP Handoff."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Collection, Protocol

from aos_api.aip_agent_registry_contracts import (
    AgentInstance,
    AgentInstanceStatus,
    HandoffEnvelopeRequest,
    IssueHandoffRequest,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.ecommerce_workshop_catalog import EcommerceWorkshopCatalog
from aos_api.ecommerce_workshop_handoff_contracts import (
    RESERVED_CONTEXT_FIELDS,
    ModuleHandoffCompileBlocker,
    ModuleHandoffCompileRequest,
    ModuleHandoffCompileResponse,
)
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TaskCockpitResponsibilityHandoffEnvelope,
    TaskCockpitResponsibilitySlot,
)
from aos_api.tenant_scope import TenantScope


class ModuleHandoffCompilerError(RuntimeError):
    code = "WORKSHOP_HANDOFF_COMPILE_ERROR"


class ModuleHandoffCompilerDrift(ModuleHandoffCompilerError):
    code = "WORKSHOP_HANDOFF_COMPILE_DRIFTED"


class ResponsibilityReader(Protocol):
    def read_responsibility_handoffs(
        self, *, org_id: str, project_id: str, run_id: str
    ) -> TaskCockpitResponsibilityHandoffEnvelope: ...


class InstanceReader(Protocol):
    def get_instance(self, scope: TenantScope, instance_id: str) -> AgentInstance: ...


class ModuleHandoffCompiler:
    """Compile an exact command; durable mutation remains in AipHandoffService."""

    def __init__(
        self,
        *,
        cockpit: ResponsibilityReader,
        catalog: EcommerceWorkshopCatalog,
        instances: InstanceReader | None = None,
        now=lambda: datetime.now(UTC),
    ) -> None:
        self._cockpit = cockpit
        self._catalog = catalog
        self._instances = instances or AipAgentRegistryStore()
        self._now = now

    def compile(
        self,
        scope: TenantScope,
        run_id: str,
        body: ModuleHandoffCompileRequest,
        *,
        roles: Collection[str],
        principal_markings: Collection[str],
    ) -> ModuleHandoffCompileResponse:
        evaluated_at = self._now()
        if evaluated_at.utcoffset() is None:
            raise ModuleHandoffCompilerDrift("compiler clock must be timezone-aware")
        if body.expires_at <= evaluated_at:
            raise ModuleHandoffCompilerDrift("handoff expiry must be in the future")
        if not set(body.markings).issubset(set(principal_markings)):
            raise ModuleHandoffCompilerDrift("handoff markings exceed principal markings")

        # Both modules must be installed and visible under the current tenant and
        # principal.  The catalog remains the sole module manifest projection.
        for module_id in (body.source_module_id, body.target_module_id):
            self._catalog.get_readiness(
                module_id=module_id,
                org_id=scope.org_id,
                project_id=scope.project_id,
                roles=roles,
                markings=principal_markings,
            )

        responsibility = self._cockpit.read_responsibility_handoffs(
            org_id=scope.org_id,
            project_id=scope.project_id,
            run_id=run_id,
        )
        if (responsibility.tenant.org_id, responsibility.tenant.project_id) != scope.key:
            raise ModuleHandoffCompilerDrift("responsibility tenant drifted")
        if body.task_ref.resource_id != responsibility.task_id or body.run_ref.resource_id != run_id:
            raise ModuleHandoffCompilerDrift("Task/TaskRun exact identity drifted")

        source = self._slot(responsibility, body.source_slot_id)
        target = self._slot(responsibility, body.target_slot_id)
        sender = self._resolve_instance(scope, source)
        receiver = self._resolve_instance(scope, target)

        blockers: list[ModuleHandoffCompileBlocker] = []
        for label, slot in (("sender", source), ("receiver", target)):
            if slot.assignee.operational_readiness != "resolved_at_observation":
                blockers.append(
                    ModuleHandoffCompileBlocker(
                        code=f"HANDOFF_{label.upper()}_NOT_OPERATIONAL",
                        dependency=f"ResponsibilitySlot:{slot.slot_id}",
                        requiredAction="refresh canonical assignee resolution and operational readiness",
                    )
                )
        for label, instance in (("sender", sender), ("receiver", receiver)):
            if instance.status is not AgentInstanceStatus.ACTIVE:
                blockers.append(
                    ModuleHandoffCompileBlocker(
                        code=f"HANDOFF_{label.upper()}_INSTANCE_NOT_ACTIVE",
                        dependency=f"AgentInstance:{instance.instance_id}",
                        requiredAction="activate the exact canonical AgentInstance after its operational gate passes",
                    )
                )

        common = dict(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            runId=run_id,
            taskId=responsibility.task_id,
            evaluatedAt=evaluated_at,
            responsibilityPlanRef=responsibility.responsibility_plan_ref,
            sourceModuleId=body.source_module_id,
            targetModuleId=body.target_module_id,
            sourceSlotId=body.source_slot_id,
            targetSlotId=body.target_slot_id,
        )
        if blockers:
            return ModuleHandoffCompileResponse(
                **common, readiness="blocked", blockers=blockers, issueCommand=None
            )

        compiled_context = dict(body.context)
        compiled_context.update(
            zip(
                RESERVED_CONTEXT_FIELDS,
                (
                    body.source_module_id,
                    body.target_module_id,
                    body.source_slot_id,
                    body.target_slot_id,
                    body.purpose,
                    body.requested_outcome,
                ),
                strict=True,
            )
        )
        allowed = [*body.allowed_context_fields, *RESERVED_CONTEXT_FIELDS]
        issue = IssueHandoffRequest(
            handoffId=body.handoff_id,
            envelope=HandoffEnvelopeRequest(
                taskRef=body.task_ref,
                runRef=body.run_ref,
                senderInstance=sender.instance_ref,
                receiverInstance=receiver.instance_ref,
                objectRefs=body.object_refs,
                artifactRefs=body.artifact_refs,
                evidenceRefs=body.evidence_refs,
                context=compiled_context,
                allowedContextFields=allowed,
                markings=body.markings,
                expiresAt=body.expires_at,
            ),
        )
        return ModuleHandoffCompileResponse(
            **common, readiness="ready", blockers=[], issueCommand=issue
        )

    @staticmethod
    def _slot(
        responsibility: TaskCockpitResponsibilityHandoffEnvelope, slot_id: str
    ) -> TaskCockpitResponsibilitySlot:
        match = next((item for item in responsibility.slots if item.slot_id == slot_id), None)
        if match is None or slot_id not in responsibility.compiled_required_slot_ids:
            raise ModuleHandoffCompilerDrift("ResponsibilitySlot is not in exact compilation")
        return match

    def _resolve_instance(self, scope: TenantScope, slot: TaskCockpitResponsibilitySlot) -> AgentInstance:
        assignee = slot.assignee
        if assignee.kind != "agent_instance":
            raise ModuleHandoffCompilerDrift("ResponsibilitySlot is not bound to AgentInstance")
        instance = self._instances.get_instance(scope, assignee.resource_id)
        if (instance.instance_id, instance.instance_ref.revision) != (assignee.resource_id, assignee.version):
            raise ModuleHandoffCompilerDrift("AgentInstance exact revision drifted from ResponsibilitySlot")
        return instance
