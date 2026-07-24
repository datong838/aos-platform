"""W2-Y · 契约与安全标记组：#88 CAP 约束 + #99 安全标记传播 + #100 标记移除策略.

本模块是 AIP 契约执行层与标记传播层三件：
    - CapConstraintEngine      CAP-01~07 7 项硬约束的注册/校验/违规记录
    - MarkingPropagationEngine stop_propagating/stop_requiring 配置 + 传播算法
    - MarkingRemovalEngine     filter_in/filter_out 移除策略 + 输出标记清理

不重写 CapabilityAdapterEngine/EgressPolicyEngine；仅作契约与标记层。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class CapAndMarkingsError(Exception):
    """W2-Y 契约与安全标记组错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════════════════════════════════════════════════
# #88 CAP 约束
# ════════════════════════════════════════════════════════════════

class CapRule(BaseModel):
    """CAP 约束规则（对齐 07b §4）。"""

    code: str                          # CAP-01 ~ CAP-07
    title: str
    description: str
    severity: str = "error"            # error / warning
    enabled: bool = True
    enforcement: str = "block"         # block / audit / dry_run


class CapViolation(BaseModel):
    """CAP 违规记录。"""

    id: str = Field(default_factory=lambda: _uid("capviol"))
    code: str                          # CAP-01 ~ CAP-07
    timestamp: float = Field(default_factory=_now_ts)
    actor: str
    target_type: str                   # function / capability / logic_run / action
    target_id: str
    detail: dict[str, Any] = Field(default_factory=dict)
    severity: str = "error"
    resolution: str = "blocked"        # blocked / audited / dry_run_passed


# 默认 7 条 CAP 规则（对齐 07b §4）
DEFAULT_CAP_RULES: list[CapRule] = [
    CapRule(
        code="CAP-01",
        title="超 FUNC-03 须 Capability",
        description="超 FUNC-03（>60s/2GB）的能力不得注册为普通 Function；须 Capability kind=job/session",
        severity="error",
        enabled=True,
        enforcement="block",
    ),
    CapRule(
        code="CAP-02",
        title="试跑默认 dry-run",
        description="Logic 试跑调用 Capability 默认 dry-run / 沙箱配额；真扣 GPU 须显式「生产试跑」权限",
        severity="warning",
        enabled=True,
        enforcement="audit",
    ),
    CapRule(
        code="CAP-03",
        title="写回仅经 Action",
        description="写 Ontology / 挂 MediaSet 仅经 Action（或官方 Edits）；Adapter 回调只投递事件，不直写库",
        severity="error",
        enabled=True,
        enforcement="block",
    ),
    CapRule(
        code="CAP-04",
        title="密钥仅 Vault",
        description="密钥与厂商 endpoint 仅 Vault；UI 只存 ref",
        severity="error",
        enabled=True,
        enforcement="block",
    ),
    CapRule(
        code="CAP-05",
        title="回调验签/DLQ",
        description="回调验签；失败进 DLQ；可人工重放（对齐 ACT-10）",
        severity="error",
        enabled=True,
        enforcement="block",
    ),
    CapRule(
        code="CAP-06",
        title="Tool 面板权限绑定",
        description="Tool 面板挂载须绑定调用用户权限（A-08）；项目范围执行须显式开关",
        severity="warning",
        enabled=True,
        enforcement="audit",
    ),
    CapRule(
        code="CAP-07",
        title="不做 Marketplace",
        description="不做 Capability Marketplace；仅组织内登记与版本发布",
        severity="warning",
        enabled=True,
        enforcement="audit",
    ),
]

_VALID_ENFORCEMENTS = {"block", "audit", "dry_run"}
_VALID_SEVERITIES = {"error", "warning"}
_MAX_VIOLATIONS = 200


class CapConstraintEngine:
    """#88 · CAP 约束引擎。"""

    def __init__(self, rules: list[CapRule] | None = None) -> None:
        self._lock = threading.Lock()
        self._rules: dict[str, CapRule] = {
            r.code: r for r in (rules or DEFAULT_CAP_RULES)
        }
        self._violations: dict[str, CapViolation] = {}
        self._order: list[str] = []

    def get_rule(self, code: str) -> CapRule:
        with self._lock:
            r = self._rules.get(code)
        if not r:
            raise CapAndMarkingsError(
                "NOT_FOUND",
                f"CAP 规则 {code} 不存在",
            )
        return r

    def list_rules(self, enabled_only: bool = False) -> list[CapRule]:
        with self._lock:
            items = list(self._rules.values())
        if enabled_only:
            items = [r for r in items if r.enabled]
        return sorted(items, key=lambda r: r.code)

    def update_rule(self, code: str, updates: dict[str, Any]) -> CapRule:
        if "code" in updates:
            raise CapAndMarkingsError(
                "IMMUTABLE_FIELD",
                "code 不可修改",
            )
        if "enforcement" in updates and updates["enforcement"] not in _VALID_ENFORCEMENTS:
            raise CapAndMarkingsError(
                "INVALID_ENFORCEMENT",
                f"未知 enforcement: {updates['enforcement']}（合法: {sorted(_VALID_ENFORCEMENTS)}）",
            )
        if "severity" in updates and updates["severity"] not in _VALID_SEVERITIES:
            raise CapAndMarkingsError(
                "INVALID_SEVERITY",
                f"未知 severity: {updates['severity']}（合法: {sorted(_VALID_SEVERITIES)}）",
            )
        with self._lock:
            r = self._rules.get(code)
            if not r:
                raise CapAndMarkingsError(
                    "NOT_FOUND",
                    f"CAP 规则 {code} 不存在",
                )
            data = r.model_dump()
            for k, v in updates.items():
                if k in data:
                    data[k] = v
            updated = CapRule(**data)
            self._rules[code] = updated
            return updated.model_copy()

    def check(
        self,
        code: str,
        actor: str,
        target_type: str,
        target_id: str,
        detail: dict[str, Any] | None = None,
    ) -> CapViolation:
        """执行约束校验：返回 CapViolation（resolution=blocked/audited/dry_run_passed）。"""
        rule = self.get_rule(code)
        if not rule.enabled:
            resolution = "dry_run_passed"
        elif rule.enforcement == "dry_run":
            resolution = "dry_run_passed"
        elif rule.enforcement == "audit":
            resolution = "audited"
        else:  # block
            resolution = "blocked"
        viol = CapViolation(
            code=code,
            actor=actor,
            target_type=target_type,
            target_id=target_id,
            detail=detail or {},
            severity=rule.severity,
            resolution=resolution,
        )
        with self._lock:
            is_new = viol.id not in self._violations
            self._violations[viol.id] = viol
            if is_new:
                self._order.append(viol.id)
            while len(self._order) > _MAX_VIOLATIONS:
                old_id = self._order.pop(0)
                self._violations.pop(old_id, None)
        return viol

    def list_violations(
        self,
        code: str | None = None,
        target_type: str | None = None,
        limit: int = 50,
    ) -> list[CapViolation]:
        with self._lock:
            items = [self._violations[i] for i in self._order]
        if code:
            items = [v for v in items if v.code == code]
        if target_type:
            items = [v for v in items if v.target_type == target_type]
        items = sorted(items, key=lambda r: r.timestamp, reverse=True)
        return items[:limit]

    def get_violation(self, violation_id: str) -> CapViolation:
        with self._lock:
            v = self._violations.get(violation_id)
        if not v:
            raise CapAndMarkingsError(
                "NOT_FOUND",
                f"违规记录 {violation_id} 不存在",
            )
        return v


# ════════════════════════════════════════════════════════════════
# #99 安全标记传播
# ════════════════════════════════════════════════════════════════

class MarkingPropagationConfig(BaseModel):
    """标记传播配置（per project/object_type）。"""

    project_id: str
    object_type: str
    stop_propagating: bool = False     # 停止向下游传播
    stop_requiring: bool = False       # 不再要求下游继承
    inherit_from_parent: bool = True   # 从父项目继承
    expand_input_inheritance: bool = False  # 展开输入继承


class MarkingRecord(BaseModel):
    """标记记录。"""

    id: str = Field(default_factory=lambda: _uid("mark"))
    project_id: str
    object_type: str
    object_id: str
    security_label: str                # public/internal/sensitive/restricted
    propagated_from: str = ""          # 来源 object_id（继承自）
    is_inherited: bool = False
    created_at: float = Field(default_factory=_now_ts)


_VALID_SECURITY_LABELS = {"public", "internal", "sensitive", "restricted"}
_MAX_MARKINGS = 200


class MarkingPropagationEngine:
    """#99 · 安全标记传播引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._configs: dict[tuple[str, str], MarkingPropagationConfig] = {}
        self._markings: dict[tuple[str, str, str], MarkingRecord] = {}
        self._order: list[tuple[str, str, str]] = []

    def set_config(self, cfg: MarkingPropagationConfig) -> MarkingPropagationConfig:
        with self._lock:
            self._configs[(cfg.project_id, cfg.object_type)] = cfg
        return cfg

    def get_config(self, project_id: str, object_type: str) -> MarkingPropagationConfig:
        with self._lock:
            cfg = self._configs.get((project_id, object_type))
        if not cfg:
            # 默认回退
            return MarkingPropagationConfig(project_id=project_id, object_type=object_type)
        return cfg.model_copy()

    def list_configs(self, project_id: str | None = None) -> list[MarkingPropagationConfig]:
        with self._lock:
            items = list(self._configs.values())
        if project_id:
            items = [c for c in items if c.project_id == project_id]
        return sorted(items, key=lambda c: (c.project_id, c.object_type))

    def record_marking(self, rec: MarkingRecord) -> MarkingRecord:
        if rec.security_label not in _VALID_SECURITY_LABELS:
            raise CapAndMarkingsError(
                "INVALID_SECURITY_LABEL",
                f"未知 security_label: {rec.security_label}（合法: {sorted(_VALID_SECURITY_LABELS)}）",
            )
        with self._lock:
            key = (rec.project_id, rec.object_type, rec.object_id)
            is_new = key not in self._markings
            self._markings[key] = rec
            if is_new:
                self._order.append(key)
            while len(self._order) > _MAX_MARKINGS:
                old_key = self._order.pop(0)
                self._markings.pop(old_key, None)
        return rec

    def get_marking(self, project_id: str, object_type: str, object_id: str) -> MarkingRecord:
        with self._lock:
            m = self._markings.get((project_id, object_type, object_id))
        if not m:
            raise CapAndMarkingsError(
                "NOT_FOUND",
                f"标记 {project_id}/{object_type}/{object_id} 不存在",
            )
        return m

    def list_markings(
        self,
        project_id: str,
        object_type: str | None = None,
        security_label: str | None = None,
        limit: int = 50,
    ) -> list[MarkingRecord]:
        with self._lock:
            items = [self._markings[k] for k in self._order]
        items = [m for m in items if m.project_id == project_id]
        if object_type:
            items = [m for m in items if m.object_type == object_type]
        if security_label:
            items = [m for m in items if m.security_label == security_label]
        items = sorted(items, key=lambda r: r.created_at, reverse=True)
        return items[:limit]

    def propagate(
        self,
        project_id: str,
        source_object_type: str,
        source_object_id: str,
        downstream_object_type: str,
        downstream_object_id: str,
    ) -> MarkingRecord:
        """传播标记：若 stop_propagating=True 则不传播；否则复制 source 的 security_label。"""
        source = self.get_marking(project_id, source_object_type, source_object_id)
        cfg = self.get_config(project_id, source_object_type)
        if cfg.stop_propagating:
            # 不传播：下游记录为非继承
            downstream = MarkingRecord(
                project_id=project_id,
                object_type=downstream_object_type,
                object_id=downstream_object_id,
                security_label="public",  # 默认 public
                propagated_from="",
                is_inherited=False,
            )
        else:
            downstream = MarkingRecord(
                project_id=project_id,
                object_type=downstream_object_type,
                object_id=downstream_object_id,
                security_label=source.security_label,
                propagated_from=source.object_id,
                is_inherited=True,
            )
        return self.record_marking(downstream)


# ════════════════════════════════════════════════════════════════
# #100 标记移除策略
# ════════════════════════════════════════════════════════════════

class MarkingRemovalPolicy(BaseModel):
    """标记移除策略。"""

    id: str = Field(default_factory=lambda: _uid("rm-pol"))
    project_id: str
    pipeline_id: str = ""
    output_object_type: str
    strategy: str                      # filter_in / filter_out
    removed_labels: list[str] = Field(default_factory=list)  # 要移除的标记列表
    keep_labels: list[str] = Field(default_factory=list)     # 仅保留的标记列表（filter_in 用）
    apply_to_inherited: bool = True    # 是否对继承标记也生效
    enabled: bool = True


class MarkingRemovalResult(BaseModel):
    """标记移除执行结果。"""

    id: str = Field(default_factory=lambda: _uid("rm-res"))
    policy_id: str
    timestamp: float = Field(default_factory=_now_ts)
    object_id: str
    original_labels: list[str]
    removed_labels: list[str]
    final_labels: list[str]
    skipped_inherited: int = 0


_VALID_STRATEGIES = {"filter_in", "filter_out"}
_MAX_RESULTS = 200


class MarkingRemovalEngine:
    """#100 · 标记移除策略引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._policies: dict[str, MarkingRemovalPolicy] = {}
        self._results: dict[str, MarkingRemovalResult] = {}
        self._res_order: list[str] = []

    def register_policy(self, policy: MarkingRemovalPolicy) -> MarkingRemovalPolicy:
        if policy.strategy not in _VALID_STRATEGIES:
            raise CapAndMarkingsError(
                "INVALID_STRATEGY",
                f"未知 strategy: {policy.strategy}（合法: {sorted(_VALID_STRATEGIES)}）",
            )
        if policy.strategy == "filter_in" and not policy.keep_labels:
            raise CapAndMarkingsError(
                "INVALID_POLICY",
                "filter_in 策略须指定 keep_labels",
            )
        if policy.strategy == "filter_out" and not policy.removed_labels:
            raise CapAndMarkingsError(
                "INVALID_POLICY",
                "filter_out 策略须指定 removed_labels",
            )
        with self._lock:
            self._policies[policy.id] = policy
        return policy

    def get_policy(self, policy_id: str) -> MarkingRemovalPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
        if not p:
            raise CapAndMarkingsError(
                "NOT_FOUND",
                f"移除策略 {policy_id} 不存在",
            )
        return p

    def list_policies(
        self,
        project_id: str | None = None,
        output_object_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[MarkingRemovalPolicy]:
        with self._lock:
            items = list(self._policies.values())
        if project_id:
            items = [p for p in items if p.project_id == project_id]
        if output_object_type:
            items = [p for p in items if p.output_object_type == output_object_type]
        if enabled_only:
            items = [p for p in items if p.enabled]
        return sorted(items, key=lambda p: p.id, reverse=True)

    def update_policy(self, policy_id: str, updates: dict[str, Any]) -> MarkingRemovalPolicy:
        if "id" in updates:
            raise CapAndMarkingsError(
                "IMMUTABLE_FIELD",
                "id 不可修改",
            )
        if "strategy" in updates and updates["strategy"] not in _VALID_STRATEGIES:
            raise CapAndMarkingsError(
                "INVALID_STRATEGY",
                f"未知 strategy: {updates['strategy']}",
            )
        with self._lock:
            p = self._policies.get(policy_id)
            if not p:
                raise CapAndMarkingsError(
                    "NOT_FOUND",
                    f"移除策略 {policy_id} 不存在",
                )
            data = p.model_dump()
            for k, v in updates.items():
                if k in data:
                    data[k] = v
            updated = MarkingRemovalPolicy(**data)
            self._policies[policy_id] = updated
            return updated.model_copy()

    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            return self._policies.pop(policy_id, None) is not None

    def apply(
        self,
        policy_id: str,
        object_id: str,
        original_labels: list[str],
        inherited_labels: list[str] | None = None,
    ) -> MarkingRemovalResult:
        """执行移除：filter_in 仅保留 keep_labels；filter_out 移除 removed_labels。"""
        policy = self.get_policy(policy_id)
        if not policy.enabled:
            raise CapAndMarkingsError(
                "POLICY_DISABLED",
                f"移除策略 {policy_id} 已禁用",
            )
        inherited_labels = inherited_labels or []
        # 区分继承与非继承
        non_inherited = [l for l in original_labels if l not in inherited_labels]
        inherited_present = [l for l in original_labels if l in inherited_labels]
        # 默认对所有 original_labels 生效
        labels_to_process = list(original_labels)
        skipped_inherited = 0
        if not policy.apply_to_inherited:
            # 仅处理非继承
            labels_to_process = non_inherited
            skipped_inherited = len(inherited_present)

        if policy.strategy == "filter_in":
            keep_set = set(policy.keep_labels)
            removed = [l for l in labels_to_process if l not in keep_set]
            final = [l for l in labels_to_process if l in keep_set]
            # 不参与处理的继承标记保留
            if not policy.apply_to_inherited:
                final = final + inherited_present
        else:  # filter_out
            remove_set = set(policy.removed_labels)
            removed = [l for l in labels_to_process if l in remove_set]
            final = [l for l in labels_to_process if l not in remove_set]
            if not policy.apply_to_inherited:
                final = final + inherited_present

        result = MarkingRemovalResult(
            policy_id=policy_id,
            object_id=object_id,
            original_labels=list(original_labels),
            removed_labels=removed,
            final_labels=final,
            skipped_inherited=skipped_inherited,
        )
        with self._lock:
            is_new = result.id not in self._results
            self._results[result.id] = result
            if is_new:
                self._res_order.append(result.id)
            while len(self._res_order) > _MAX_RESULTS:
                old_id = self._res_order.pop(0)
                self._results.pop(old_id, None)
        return result

    def list_results(
        self,
        policy_id: str | None = None,
        limit: int = 50,
    ) -> list[MarkingRemovalResult]:
        with self._lock:
            items = [self._results[i] for i in self._res_order]
        if policy_id:
            items = [r for r in items if r.policy_id == policy_id]
        items = sorted(items, key=lambda r: r.timestamp, reverse=True)
        return items[:limit]


# ────────────────────────────────────────────────────────────────
# 单例
# ────────────────────────────────────────────────────────────────

_cap_constraint_engine: CapConstraintEngine | None = None
_cap_constraint_lock = threading.Lock()


def get_cap_constraint_engine() -> CapConstraintEngine:
    """获取 CapConstraintEngine 单例（双重检查锁）。"""
    global _cap_constraint_engine
    if _cap_constraint_engine is None:
        with _cap_constraint_lock:
            if _cap_constraint_engine is None:
                _cap_constraint_engine = CapConstraintEngine()
    return _cap_constraint_engine


_marking_propagation_engine: MarkingPropagationEngine | None = None
_marking_propagation_lock = threading.Lock()


def get_marking_propagation_engine() -> MarkingPropagationEngine:
    """获取 MarkingPropagationEngine 单例（双重检查锁）。"""
    global _marking_propagation_engine
    if _marking_propagation_engine is None:
        with _marking_propagation_lock:
            if _marking_propagation_engine is None:
                _marking_propagation_engine = MarkingPropagationEngine()
    return _marking_propagation_engine


_marking_removal_engine: MarkingRemovalEngine | None = None
_marking_removal_lock = threading.Lock()


def get_marking_removal_engine() -> MarkingRemovalEngine:
    """获取 MarkingRemovalEngine 单例（双重检查锁）。"""
    global _marking_removal_engine
    if _marking_removal_engine is None:
        with _marking_removal_lock:
            if _marking_removal_engine is None:
                _marking_removal_engine = MarkingRemovalEngine()
    return _marking_removal_engine
