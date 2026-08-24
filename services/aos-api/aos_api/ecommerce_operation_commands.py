"""Read-only W3-12B command readiness for the Operations cockpit."""

from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_operation_command_contracts import (
    OperationCommandBlocker,
    OperationCommandDescriptor,
    OperationCommandId,
    OperationCommandReadinessEnvelope,
    OperationCommandRisk,
    OperationCommandSideEffect,
    OperationCommandStatus,
)


_INTERNAL_BLOCKER = OperationCommandBlocker(
    code="OPERATION_COMMAND_HANDLER_NOT_BOUND",
    dependency="W3-12B2",
    required_action="接入 expectedVersion、幂等 Receipt 与内部 authority command handler",
)
_GOVERNANCE_BLOCKER = OperationCommandBlocker(
    code="PROPOSAL_APPROVAL_LEASE_NOT_BOUND",
    dependency="canonical action governance",
    required_action="绑定 exact Proposal、Approval、ExecutionLease 与 Receipt 后重新核验",
)
_EXTERNAL_BLOCKER = OperationCommandBlocker(
    code="EXTERNAL_ACTION_GATE_NOT_BOUND",
    dependency="refund action authority",
    required_action="完成资金动作专项门、maker-checker 与 unknown reconcile 后重新核验",
)


class EcommerceOperationCommands:
    """Returns deterministic fail-closed readiness without mutating authority."""

    def read_readiness(
        self, *, org_id: str, project_id: str
    ) -> OperationCommandReadinessEnvelope:
        tenant = TenantContext(org_id=org_id, project_id=project_id)
        definitions = (
            (OperationCommandId.CLASSIFY, "分类事件", OperationCommandRisk.CONTROLLED),
            (OperationCommandId.CREATE_CASE, "创建运营工单", OperationCommandRisk.CONTROLLED),
            (
                OperationCommandId.CHANGE_MEMBERSHIP,
                "调整工单成员",
                OperationCommandRisk.CONTROLLED,
            ),
            (OperationCommandId.MANAGE_SLA, "管理 SLA", OperationCommandRisk.CONTROLLED),
        )
        commands = [
            OperationCommandDescriptor(
                command_id=command_id,
                label=label,
                status=OperationCommandStatus.BLOCKED,
                risk=risk,
                side_effect=OperationCommandSideEffect.INTERNAL_AUTHORITY,
                blockers=[_INTERNAL_BLOCKER],
            )
            for command_id, label, risk in definitions
        ]
        commands.extend(
            [
                OperationCommandDescriptor(
                    command_id=OperationCommandId.AUTOMATION_KILL,
                    label="自动化 Kill",
                    status=OperationCommandStatus.BLOCKED,
                    risk=OperationCommandRisk.HIGH,
                    side_effect=OperationCommandSideEffect.INTERNAL_AUTHORITY,
                    blockers=[_GOVERNANCE_BLOCKER],
                ),
                OperationCommandDescriptor(
                    command_id=OperationCommandId.REFUND,
                    label="退款",
                    status=OperationCommandStatus.BLOCKED,
                    risk=OperationCommandRisk.HIGH,
                    side_effect=OperationCommandSideEffect.EXTERNAL,
                    blockers=[_EXTERNAL_BLOCKER],
                ),
            ]
        )
        return OperationCommandReadinessEnvelope(
            tenant=tenant,
            evaluated_at=datetime.now(UTC),
            commands=commands,
        )


__all__ = ["EcommerceOperationCommands"]
