"""W2-Y · 契约与安全标记组路由：#88 CAP 约束 + #99 安全标记传播 + #100 标记移除策略."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.cap_and_markings import (
    CapAndMarkingsError,
    MarkingPropagationConfig,
    MarkingRecord,
    MarkingRemovalPolicy,
    get_cap_constraint_engine,
    get_marking_propagation_engine,
    get_marking_removal_engine,
)
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["cap-and-markings"])
log = get_logger("aos-api.cap-and-markings")


def _map_err(err: CapAndMarkingsError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #88 CAP 约束 ════════════════════

class CapRuleUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    enabled: bool | None = None
    enforcement: str | None = None


class CapCheckIn(BaseModel):
    code: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    detail: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/aip/cap-constraints/rules")
def list_cap_rules(
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#88 · 列出 CAP 规则。"""
    _ = principal
    items = get_cap_constraint_engine().list_rules(enabled_only=enabled_only)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/aip/cap-constraints/rules/{code}")
def get_cap_rule(
    code: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#88 · 单条 CAP 规则。"""
    _ = principal
    try:
        return {"item": get_cap_constraint_engine().get_rule(code).model_dump()}
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/aip/cap-constraints/rules/{code}")
def update_cap_rule(
    code: str,
    body: CapRuleUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#88 · 更新 CAP 规则。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        r = get_cap_constraint_engine().update_rule(code, updates)
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.post("/v1/aip/cap-constraints/check")
def check_cap(
    body: CapCheckIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#88 · 执行约束校验。"""
    _ = principal
    try:
        v = get_cap_constraint_engine().check(
            code=body.code,
            actor=body.actor,
            target_type=body.target_type,
            target_id=body.target_id,
            detail=body.detail,
        )
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc
    return {"item": v.model_dump()}


@router.get("/v1/aip/cap-constraints/violations")
def list_cap_violations(
    code: str | None = None,
    target_type: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#88 · 违规列表。"""
    _ = principal
    items = get_cap_constraint_engine().list_violations(
        code=code, target_type=target_type, limit=limit,
    )
    return {"items": [v.model_dump() for v in items], "count": len(items)}


@router.get("/v1/aip/cap-constraints/violations/{violation_id}")
def get_cap_violation(
    violation_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#88 · 单条违规。"""
    _ = principal
    try:
        return {"item": get_cap_constraint_engine().get_violation(violation_id).model_dump()}
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc


# ════════════════════ #99 安全标记传播 ════════════════════

class PropagationConfigIn(BaseModel):
    project_id: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    stop_propagating: bool = False
    stop_requiring: bool = False
    inherit_from_parent: bool = True
    expand_input_inheritance: bool = False


class MarkingRecordIn(BaseModel):
    project_id: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    security_label: str
    propagated_from: str = ""
    is_inherited: bool = False


class PropagateIn(BaseModel):
    project_id: str = Field(min_length=1)
    source_object_type: str = Field(min_length=1)
    source_object_id: str = Field(min_length=1)
    downstream_object_type: str = Field(min_length=1)
    downstream_object_id: str = Field(min_length=1)


@router.post("/v1/aip/markings/propagation-configs")
def set_propagation_config(
    body: PropagationConfigIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#99 · 设置传播配置。"""
    _ = principal
    cfg = get_marking_propagation_engine().set_config(
        MarkingPropagationConfig(**body.model_dump()),
    )
    return {"item": cfg.model_dump()}


@router.get("/v1/aip/markings/propagation-configs")
def list_propagation_configs(
    project_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#99 · 传播配置列表。"""
    _ = principal
    items = get_marking_propagation_engine().list_configs(project_id=project_id)
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.get("/v1/aip/markings/propagation-configs/{project_id}/{object_type}")
def get_propagation_config(
    project_id: str,
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#99 · 单条传播配置。"""
    _ = principal
    cfg = get_marking_propagation_engine().get_config(project_id, object_type)
    return {"item": cfg.model_dump()}


@router.post("/v1/aip/markings/records")
def record_marking(
    body: MarkingRecordIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#99 · 记录标记。"""
    _ = principal
    try:
        m = get_marking_propagation_engine().record_marking(
            MarkingRecord(**body.model_dump()),
        )
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc
    return {"item": m.model_dump()}


@router.get("/v1/aip/markings/records")
def list_markings(
    project_id: str,
    object_type: str | None = None,
    security_label: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#99 · 标记列表。"""
    _ = principal
    items = get_marking_propagation_engine().list_markings(
        project_id=project_id,
        object_type=object_type,
        security_label=security_label,
        limit=limit,
    )
    return {"items": [m.model_dump() for m in items], "count": len(items)}


@router.get("/v1/aip/markings/records/{project_id}/{object_type}/{object_id}")
def get_marking(
    project_id: str,
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#99 · 单条标记。"""
    _ = principal
    try:
        return {"item": get_marking_propagation_engine().get_marking(
            project_id, object_type, object_id,
        ).model_dump()}
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc


@router.post("/v1/aip/markings/propagate")
def propagate_marking(
    body: PropagateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#99 · 执行传播。"""
    _ = principal
    try:
        m = get_marking_propagation_engine().propagate(
            project_id=body.project_id,
            source_object_type=body.source_object_type,
            source_object_id=body.source_object_id,
            downstream_object_type=body.downstream_object_type,
            downstream_object_id=body.downstream_object_id,
        )
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc
    return {"item": m.model_dump()}


# ════════════════════ #100 标记移除策略 ════════════════════

class RemovalPolicyIn(BaseModel):
    project_id: str = Field(min_length=1)
    pipeline_id: str = ""
    output_object_type: str = Field(min_length=1)
    strategy: str
    removed_labels: list[str] = Field(default_factory=list)
    keep_labels: list[str] = Field(default_factory=list)
    apply_to_inherited: bool = True
    enabled: bool = True


class RemovalPolicyUpdateIn(BaseModel):
    pipeline_id: str | None = None
    output_object_type: str | None = None
    strategy: str | None = None
    removed_labels: list[str] | None = None
    keep_labels: list[str] | None = None
    apply_to_inherited: bool | None = None
    enabled: bool | None = None


class ApplyRemovalIn(BaseModel):
    object_id: str = Field(min_length=1)
    original_labels: list[str] = Field(default_factory=list)
    inherited_labels: list[str] = Field(default_factory=list)


@router.post("/v1/aip/markings/removal-policies")
def register_removal_policy(
    body: RemovalPolicyIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#100 · 注册移除策略。"""
    _ = principal
    try:
        p = get_marking_removal_engine().register_policy(
            MarkingRemovalPolicy(**body.model_dump()),
        )
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.get("/v1/aip/markings/removal-policies")
def list_removal_policies(
    project_id: str | None = None,
    output_object_type: str | None = None,
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#100 · 移除策略列表。"""
    _ = principal
    items = get_marking_removal_engine().list_policies(
        project_id=project_id,
        output_object_type=output_object_type,
        enabled_only=enabled_only,
    )
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.get("/v1/aip/markings/removal-policies/{policy_id}")
def get_removal_policy(
    policy_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#100 · 单条移除策略。"""
    _ = principal
    try:
        return {"item": get_marking_removal_engine().get_policy(policy_id).model_dump()}
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/aip/markings/removal-policies/{policy_id}")
def update_removal_policy(
    policy_id: str,
    body: RemovalPolicyUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#100 · 更新移除策略。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        p = get_marking_removal_engine().update_policy(policy_id, updates)
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.delete("/v1/aip/markings/removal-policies/{policy_id}")
def delete_removal_policy(
    policy_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#100 · 删除移除策略。"""
    _ = principal
    ok = get_marking_removal_engine().delete_policy(policy_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"策略 {policy_id} 不存在", status_code=404)
    return {"id": policy_id, "deleted": True}


@router.post("/v1/aip/markings/removal-policies/{policy_id}/apply")
def apply_removal_policy(
    policy_id: str,
    body: ApplyRemovalIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#100 · 执行移除。"""
    _ = principal
    try:
        r = get_marking_removal_engine().apply(
            policy_id=policy_id,
            object_id=body.object_id,
            original_labels=body.original_labels,
            inherited_labels=body.inherited_labels,
        )
    except CapAndMarkingsError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.get("/v1/aip/markings/removal-results")
def list_removal_results(
    policy_id: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#100 · 移除结果列表。"""
    _ = principal
    items = get_marking_removal_engine().list_results(policy_id=policy_id, limit=limit)
    return {"items": [r.model_dump() for r in items], "count": len(items)}
