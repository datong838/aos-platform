"""W2-T · k-LLM 路由编排组：#71 智能路由 + #72 场景化路由 + #73 熔断/热切换.

本模块是 ``aos_api.llm_gateway.chat()`` 之上的策略层编排：
    - SmartRouter      按请求特征自动选模型
    - ScenarioRouter   按任务类型 / 块级选模
    - FailoverEngine   熔断器状态机 + 主备热切换
    - LLMRoutingFacade 组合三引擎，端到端智能路由调用

底层网关 ``chat(query, model=X)`` 不重写，仅作为调用出口。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class RoutingError(Exception):
    """路由编排层错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ────────────────────────────────────────────────────────────────
# #71 智能路由 — 数据模型
# ────────────────────────────────────────────────────────────────

class ModelCandidate(BaseModel):
    """智能路由候选模型。"""

    id: str
    tier: str = "mid"               # low / mid / high
    max_context: int = 8192
    modalities: list[str] = Field(default_factory=lambda: ["text"])
    cost_per_1k: float = 0.0
    egress: str = "allow"           # allow / restricted / forbidden
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class RoutingRequest(BaseModel):
    """智能路由请求。"""

    query: str = ""
    context_length: int = 0
    complexity: int = 1             # 1-5
    tools_required: list[str] = Field(default_factory=list)
    security_label: str = "internal"   # public / internal / sensitive / restricted
    cost_budget: float | None = None
    preferred_modalities: list[str] = Field(default_factory=lambda: ["text"])
    prefer_tags: list[str] = Field(default_factory=list)


# 评分权重常量（集中定义，便于后续调参）
W_CAPABILITY = 0.30
W_CONTEXT = 0.25
W_COST = 0.15
W_SECURITY = 0.20
W_TAG = 0.10

_TIER_RANK = {"low": 1, "mid": 2, "high": 3}
_SECURITY_RANK = {"public": 0, "internal": 1, "sensitive": 2, "restricted": 3}
_EGRESS_RANK = {"allow": 0, "restricted": 1, "forbidden": 2}


def _capability_match(tier: str, complexity: int) -> float:
    """complexity 1-5 → 期望 tier rank；越接近满分越高。"""
    expected = 1 if complexity <= 1 else (2 if complexity <= 3 else 3)
    got = _TIER_RANK.get(tier, 2)
    if got == expected:
        return 1.0
    if got > expected:
        # 能力过剩轻微扣分（成本/延迟可能更高）
        return 0.85
    # 能力不足严重扣分
    return 0.3


def _context_fit(max_context: int, context_length: int) -> float:
    if context_length <= 0:
        return 1.0
    if max_context < context_length:
        return 0.0
    # 留 20% 余量最佳
    headroom = max_context - context_length
    if headroom >= 0.2 * max_context:
        return 1.0
    return 0.6 + 0.4 * (headroom / (0.2 * max_context))


def _cost_score(cost_per_1k: float, context_length: int, cost_budget: float | None) -> float:
    if cost_budget is None or cost_budget <= 0:
        # 无预算约束时，越便宜越好（归一化）
        if cost_per_1k <= 0:
            return 1.0
        # 0~0.01 USD/1k → 1.0~0.5
        return max(0.2, 1.0 - cost_per_1k * 50)
    projected = cost_per_1k * max(context_length, 1) / 1000
    if projected > cost_budget:
        return 0.0
    # 用了越少预算分越高
    return 1.0 - 0.5 * (projected / cost_budget)


def _security_match(egress: str, security_label: str) -> float:
    label_rank = _SECURITY_RANK.get(security_label, 1)
    egr_rank = _EGRESS_RANK.get(egress, 0)
    if egr_rank >= label_rank:
        return 1.0
    return 0.0


def _tag_overlap(tags: list[str], prefer_tags: list[str]) -> float:
    if not prefer_tags:
        return 0.5  # 中性
    if not tags:
        return 0.0
    hit = len(set(tags) & set(prefer_tags))
    return hit / len(set(prefer_tags))


class SmartRouter:
    """#71 · 按请求特征评分选模型。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._candidates: dict[str, ModelCandidate] = {}

    def register(self, candidate: ModelCandidate) -> ModelCandidate:
        with self._lock:
            self._candidates[candidate.id] = candidate
        return candidate

    def unregister(self, model_id: str) -> bool:
        with self._lock:
            return self._candidates.pop(model_id, None) is not None

    def list(self, enabled_only: bool = False) -> list[ModelCandidate]:
        with self._lock:
            items = list(self._candidates.values())
        if enabled_only:
            items = [c for c in items if c.enabled]
        return items

    def choose(self, request: RoutingRequest) -> dict[str, Any]:
        """评分选模。返回 {model_id, reason, score, alternatives, score_breakdown}."""
        candidates = self.list(enabled_only=True)

        # 硬过滤
        viable: list[ModelCandidate] = []
        for c in candidates:
            if c.max_context < request.context_length:
                continue
            if not set(c.modalities) & set(request.preferred_modalities or ["text"]):
                continue
            if request.security_label == "restricted" and c.egress != "forbidden":
                continue
            if (
                request.cost_budget is not None
                and request.cost_budget > 0
                and c.cost_per_1k * max(request.context_length, 1) / 1000 > request.cost_budget
            ):
                continue
            viable.append(c)

        if not viable:
            raise RoutingError(
                "NO_CANDIDATE",
                "无候选模型满足请求约束（上下文/模态/安全/预算）",
            )

        scored: list[tuple[float, ModelCandidate, dict[str, float], list[str]]] = []
        for c in viable:
            breakdown = {
                "capability": _capability_match(c.tier, request.complexity) * W_CAPABILITY,
                "context": _context_fit(c.max_context, request.context_length) * W_CONTEXT,
                "cost": _cost_score(c.cost_per_1k, request.context_length, request.cost_budget) * W_COST,
                "security": _security_match(c.egress, request.security_label) * W_SECURITY,
                "tag": _tag_overlap(c.tags, request.prefer_tags) * W_TAG,
            }
            score = sum(breakdown.values())
            reasons: list[str] = []
            reasons.append(f"tier={c.tier}/complexity={request.complexity}")
            reasons.append(f"context={c.max_context}/{request.context_length}")
            reasons.append(f"egress={c.egress}/label={request.security_label}")
            if request.cost_budget is not None:
                reasons.append(f"cost={c.cost_per_1k}/budget={request.cost_budget}")
            if request.prefer_tags:
                reasons.append(f"tags={c.tags}/prefer={request.prefer_tags}")
            scored.append((score, c, breakdown, reasons))

        scored.sort(key=lambda x: -x[0])
        best_score, best, best_breakdown, best_reasons = scored[0]
        alternatives = [
            {"model_id": c.id, "score": round(s, 4)}
            for s, c, _, _ in scored[1:]
        ]
        return {
            "model_id": best.id,
            "reason": " / ".join(best_reasons),
            "score": round(best_score, 4),
            "alternatives": alternatives,
            "score_breakdown": {k: round(v, 4) for k, v in best_breakdown.items()},
        }


# ────────────────────────────────────────────────────────────────
# #72 场景化路由 — 数据模型 & 引擎
# ────────────────────────────────────────────────────────────────

_VALID_TASK_TYPES = {
    "chat", "code", "math", "vision",
    "extract", "summarize", "wiki_qa",
    "pii", "provider_down", "logic_long", "chatbot",
}
_VALID_EGRESS = {"禁公网", "审批后", "继承", "强制不出域", "fallback"}


class RouteRule(BaseModel):
    """场景化路由规则，对齐 81 §2.1 RouteRule。"""

    id: str
    task: str
    task_type: str
    primary: str = "—"
    fallback: str = ""
    egress: str = "继承"
    span: bool = False
    enabled: bool = True


class BlockRoute(BaseModel):
    """块级选模绑定。"""

    block_id: str
    logic_id: str = ""
    model_id: str
    task_type: str = ""
    inherit: bool = False


class ScenarioRouter:
    """#72 · 按任务类型/块级选模。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: dict[str, RouteRule] = {}
        self._blocks: dict[str, BlockRoute] = {}

    # —— RouteRule CRUD ——
    def upsert_rule(self, rule: RouteRule) -> RouteRule:
        if rule.task_type not in _VALID_TASK_TYPES:
            raise RoutingError(
                "INVALID_TASK_TYPE",
                f"未知任务类型: {rule.task_type}（合法: {sorted(_VALID_TASK_TYPES)}）",
            )
        if rule.egress not in _VALID_EGRESS:
            raise RoutingError(
                "INVALID_EGRESS",
                f"未知 egress: {rule.egress}（合法: {sorted(_VALID_EGRESS)}）",
            )
        with self._lock:
            self._rules[rule.id] = rule
        return rule

    def get_rule(self, rule_id: str) -> RouteRule:
        with self._lock:
            r = self._rules.get(rule_id)
        if not r:
            raise RoutingError("NOT_FOUND", f"路由规则 {rule_id} 不存在")
        return r

    def list_rules(self, task_type: str | None = None) -> list[RouteRule]:
        with self._lock:
            items = list(self._rules.values())
        if task_type:
            items = [r for r in items if r.task_type == task_type]
        return items

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(rule_id, None) is not None

    # —— BlockRoute CRUD ——
    def upsert_block(self, block: BlockRoute) -> BlockRoute:
        with self._lock:
            self._blocks[block.block_id] = block
        return block

    def get_block(self, block_id: str) -> BlockRoute:
        with self._lock:
            b = self._blocks.get(block_id)
        if not b:
            raise RoutingError("NOT_FOUND", f"块路由 {block_id} 不存在")
        return b

    def list_blocks(self, logic_id: str | None = None) -> list[BlockRoute]:
        with self._lock:
            items = list(self._blocks.values())
        if logic_id:
            items = [b for b in items if b.logic_id == logic_id]
        return items

    def delete_block(self, block_id: str) -> bool:
        with self._lock:
            return self._blocks.pop(block_id, None) is not None

    # —— 解析 ——
    def resolve(self, task_type: str, block_id: str | None = None) -> dict[str, Any]:
        """返回 {primary, fallback, egress, source}."""
        # 1. 块级优先
        if block_id:
            with self._lock:
                b = self._blocks.get(block_id)
            if b and not b.inherit:
                return {
                    "primary": b.model_id,
                    "fallback": "",
                    "egress": "继承",
                    "source": "block",
                    "block_id": b.block_id,
                }

        # 2. 场景命中
        with self._lock:
            rule = next(
                (r for r in self._rules.values()
                 if r.task_type == task_type and r.enabled),
                None,
            )
        if rule:
            return {
                "primary": rule.primary,
                "fallback": rule.fallback,
                "egress": rule.egress,
                "source": "scenario",
                "rule_id": rule.id,
            }

        # 3. 默认回落
        try:
            from aos_api.gateway_default import get_gateway_default

            gd = get_gateway_default()
            default_model = str(gd.get("defaultModel") or "").strip() or "—"
        except Exception:  # noqa: BLE001
            default_model = "—"
        return {
            "primary": default_model,
            "fallback": "",
            "egress": "继承",
            "source": "default",
        }

    # —— 与 81 协议对齐 ——
    def export_rules(self) -> list[dict[str, Any]]:
        with self._lock:
            return [r.model_dump() for r in self._rules.values()]

    def import_rules(self, items: list[dict[str, Any]]) -> list[RouteRule]:
        imported: list[RouteRule] = []
        with self._lock:
            for raw in items:
                rid = str(raw.get("id") or "").strip()
                if not rid:
                    continue
                rule = RouteRule(
                    id=rid,
                    task=str(raw.get("task") or rid),
                    task_type=str(raw.get("task_type") or "chat"),
                    primary=str(raw.get("primary") or "—"),
                    fallback=str(raw.get("fallback") or ""),
                    egress=str(raw.get("egress") or "继承"),
                    span=bool(raw.get("span")),
                    enabled=bool(raw.get("enabled", True)),
                )
                self._rules[rule.id] = rule
                imported.append(rule)
        return imported


# ────────────────────────────────────────────────────────────────
# #73 熔断/热切换 — 数据模型 & 引擎
# ────────────────────────────────────────────────────────────────

class CircuitState(BaseModel):
    """熔断器状态。"""

    model_id: str
    state: str = "closed"           # closed / open / half_open
    consecutive_failures: int = 0
    last_failure_at: float = 0.0
    opened_at: float = 0.0
    half_open_probes: int = 0
    half_open_successes: int = 0


class CircuitConfig(BaseModel):
    """熔断器配置（per-model 可覆盖）。"""

    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    half_open_max_probes: int = 1
    success_threshold: int = 1


class CallRecord(BaseModel):
    """调用记录，用于审计与决策。"""

    id: str = Field(default_factory=lambda: _uid("call"))
    model_id: str
    route_source: str = "explicit"  # smart / scenario / block / explicit / failover
    success: bool
    latency_ms: int = 0
    error: str = ""
    fallback_used: bool = False
    timestamp: float = Field(default_factory=_now_ts)


_DEFAULT_CIRCUIT_CONFIG = CircuitConfig()
_MAX_CALL_RECORDS = 200


class FailoverEngine:
    """#73 · 熔断器状态机 + 主备热切换.

    通过 ``chat_callable`` 注入底层调用入口，默认使用
    ``aos_api.llm_gateway.chat``；测试时可替换为 mock。
    """

    def __init__(
        self,
        chat_callable: Callable[..., dict[str, Any]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, CircuitState] = {}
        self._configs: dict[str, CircuitConfig] = {}
        self._records: list[CallRecord] = []
        self._chat = chat_callable  # lazy resolve if None
        self._clock = clock or _now_ts

    def _resolve_chat(self) -> Callable[..., dict[str, Any]]:
        if self._chat is not None:
            return self._chat
        from aos_api.llm_gateway import chat as _chat
        self._chat = _chat
        return self._chat

    # —— 状态查询 ——
    def get_state(self, model_id: str) -> CircuitState:
        with self._lock:
            st = self._states.get(model_id)
            if st is None:
                return CircuitState(model_id=model_id)
            # 进入 half_open 探测时返回当前视图
            return st.model_copy(deep=True)

    def list_states(self) -> list[CircuitState]:
        with self._lock:
            return [s.model_copy(deep=True) for s in self._states.values()]

    def get_config(self, model_id: str) -> CircuitConfig:
        with self._lock:
            return self._configs.get(model_id, _DEFAULT_CIRCUIT_CONFIG).model_copy(deep=True)

    def set_config(self, model_id: str, config: CircuitConfig) -> CircuitConfig:
        with self._lock:
            self._configs[model_id] = config
        return config

    def reset(self, model_id: str) -> CircuitState:
        with self._lock:
            st = CircuitState(model_id=model_id)
            self._states[model_id] = st
            return st.model_copy(deep=True)

    # —— 调用记录 ——
    def record_call(
        self,
        model_id: str,
        success: bool,
        error: str = "",
        latency_ms: int = 0,
        route_source: str = "explicit",
        fallback_used: bool = False,
    ) -> CallRecord:
        rec = CallRecord(
            model_id=model_id,
            route_source=route_source,
            success=success,
            latency_ms=latency_ms,
            error=error,
            fallback_used=fallback_used,
        )
        with self._lock:
            st = self._states.setdefault(model_id, CircuitState(model_id=model_id))
            cfg = self._configs.get(model_id, _DEFAULT_CIRCUIT_CONFIG)

            if success:
                if st.state == "half_open":
                    st.half_open_successes += 1
                    if st.half_open_successes >= cfg.success_threshold:
                        st.state = "closed"
                        st.consecutive_failures = 0
                        st.half_open_probes = 0
                        st.half_open_successes = 0
                        st.opened_at = 0.0
                else:
                    # closed 状态下成功直接重置失败计数
                    st.consecutive_failures = 0
            else:
                st.last_failure_at = self._clock()
                if st.state == "half_open":
                    # 探测失败 → 重新进入 open
                    st.state = "open"
                    st.opened_at = self._clock()
                    st.half_open_probes = 0
                    st.half_open_successes = 0
                else:
                    st.consecutive_failures += 1
                    if st.consecutive_failures >= cfg.failure_threshold:
                        st.state = "open"
                        st.opened_at = self._clock()

            self._records.append(rec)
            if len(self._records) > _MAX_CALL_RECORDS:
                self._records = self._records[-_MAX_CALL_RECORDS:]
        return rec

    def list_records(
        self,
        model_id: str | None = None,
        limit: int = 50,
    ) -> list[CallRecord]:
        with self._lock:
            items = list(self._records)
        if model_id:
            items = [r for r in items if r.model_id == model_id]
        # 最近 limit 条
        return list(reversed(items[-limit:]))

    # —— 熔断器查询 ——
    def can_call(self, model_id: str) -> bool:
        """是否允许调用（含 half_open 探测配额检查与冷却推进）。"""
        with self._lock:
            st = self._states.get(model_id)
            cfg = self._configs.get(model_id, _DEFAULT_CIRCUIT_CONFIG)
            if st is None or st.state == "closed":
                return True
            now = self._clock()
            if st.state == "open":
                # 冷却到期 → 推进到 half_open
                if now - st.opened_at >= cfg.cooldown_seconds:
                    st.state = "half_open"
                    st.half_open_probes = 0
                    st.half_open_successes = 0
                    return True
                return False
            if st.state == "half_open":
                return st.half_open_probes < cfg.half_open_max_probes
            return True

    def _reserve_probe(self, model_id: str) -> bool:
        """half_open 状态下预留一个探测配额。返回是否成功预留。"""
        with self._lock:
            st = self._states.setdefault(model_id, CircuitState(model_id=model_id))
            cfg = self._configs.get(model_id, _DEFAULT_CIRCUIT_CONFIG)
            if st.state == "half_open" and st.half_open_probes < cfg.half_open_max_probes:
                st.half_open_probes += 1
                return True
            return False

    # —— 主备热切换 ——
    def call_with_failover(
        self,
        query: str,
        primary: str,
        fallback: str = "",
        route_source: str = "explicit",
    ) -> dict[str, Any]:
        """主模可调 → 调主模；失败或熔断 → 切 fallback；都失败抛 RoutingError.

        返回 {answer, model, fallback_used, route_source, call_record_id}
        """
        chat = self._resolve_chat()
        primary_call_allowed = self.can_call(primary)

        if primary_call_allowed:
            # half_open 时需要预留探测配额
            reserved = self._reserve_probe(primary)
            # closed 状态下 reserve_probe 返回 False 是正常的，仅在 half_open 时才需要
            try:
                t0 = self._clock()
                result = chat(query, model=primary)
                latency = int((self._clock() - t0) * 1000)
                rec = self.record_call(
                    primary, success=True, latency_ms=latency,
                    route_source=route_source, fallback_used=False,
                )
                return {
                    "answer": result.get("answer", ""),
                    "model": primary,
                    "fallback_used": False,
                    "route_source": route_source,
                    "call_record_id": rec.id,
                    "raw": result,
                }
            except Exception as exc:  # noqa: BLE001
                latency = int((self._clock() - t0) * 1000)
                self.record_call(
                    primary, success=False, error=str(exc), latency_ms=latency,
                    route_source=route_source, fallback_used=False,
                )
                # 进入 fallback 分支
                _ = reserved  # noqa: F841
        # else: 主模熔断或配额满 → 直接走 fallback

        # —— fallback 分支 ——
        if not fallback or fallback == "—":
            raise RoutingError(
                "PRIMARY_FAILED_NO_FALLBACK",
                f"主模型 {primary} 不可用且无回退模型",
            )

        if not self.can_call(fallback):
            raise RoutingError(
                "FALLBACK_OPEN",
                f"主模型 {primary} 失败，回退模型 {fallback} 亦处于熔断状态",
            )

        # fallback 也要预留 half_open 探测配额
        self._reserve_probe(fallback)
        try:
            t0 = self._clock()
            result = chat(query, model=fallback)
            latency = int((self._clock() - t0) * 1000)
            rec = self.record_call(
                fallback, success=True, latency_ms=latency,
                route_source="failover", fallback_used=True,
            )
            return {
                "answer": result.get("answer", ""),
                "model": fallback,
                "fallback_used": True,
                "route_source": "failover",
                "call_record_id": rec.id,
                "raw": result,
            }
        except Exception as exc:  # noqa: BLE001
            latency = int((self._clock() - t0) * 1000)
            self.record_call(
                fallback, success=False, error=str(exc), latency_ms=latency,
                route_source="failover", fallback_used=True,
            )
            raise RoutingError(
                "ALL_FAILED",
                f"主模型 {primary} 与回退模型 {fallback} 均失败：{exc}",
            ) from exc


# ────────────────────────────────────────────────────────────────
# LLMRoutingFacade — 端到端编排
# ────────────────────────────────────────────────────────────────

class LLMRoutingFacade:
    """组合 SmartRouter / ScenarioRouter / FailoverEngine."""

    def __init__(
        self,
        smart: SmartRouter | None = None,
        scenario: ScenarioRouter | None = None,
        failover: FailoverEngine | None = None,
    ) -> None:
        self.smart = smart or SmartRouter()
        self.scenario = scenario or ScenarioRouter()
        self.failover = failover or FailoverEngine()

    def smart_route_and_call(self, request: RoutingRequest) -> dict[str, Any]:
        """SmartRouter.choose → FailoverEngine.call_with_failover.

        若选出的最优模型有 alternatives，则取第一个作为 fallback。
        """
        decision = self.smart.choose(request)
        primary = decision["model_id"]
        alternatives = decision.get("alternatives") or []
        fallback = alternatives[0]["model_id"] if alternatives else ""
        result = self.failover.call_with_failover(
            request.query, primary=primary, fallback=fallback,
            route_source="smart",
        )
        result["routing_decision"] = decision
        return result

    def scenario_route_and_call(
        self,
        task_type: str,
        query: str,
        block_id: str | None = None,
    ) -> dict[str, Any]:
        """ScenarioRouter.resolve → FailoverEngine.call_with_failover."""
        decision = self.scenario.resolve(task_type, block_id=block_id)
        primary = decision.get("primary") or "—"
        fallback = decision.get("fallback") or ""
        if primary == "—":
            raise RoutingError(
                "NO_PRIMARY",
                f"任务类型 {task_type} 未配置主模型，且无默认模型可用",
            )
        result = self.failover.call_with_failover(
            query, primary=primary, fallback=fallback,
            route_source="block" if decision.get("source") == "block" else "scenario",
        )
        result["routing_decision"] = decision
        return result


# ────────────────────────────────────────────────────────────────
# 单例 getters（双重检查锁，与 ActionLogEngine/SagaEngine 一致）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_smart_router: SmartRouter | None = None
_scenario_router: ScenarioRouter | None = None
_failover_engine: FailoverEngine | None = None
_facade: LLMRoutingFacade | None = None


def get_smart_router() -> SmartRouter:
    global _smart_router
    if _smart_router is None:
        with _lock:
            if _smart_router is None:
                _smart_router = SmartRouter()
    return _smart_router


def get_scenario_router() -> ScenarioRouter:
    global _scenario_router
    if _scenario_router is None:
        with _lock:
            if _scenario_router is None:
                _scenario_router = ScenarioRouter()
    return _scenario_router


def get_failover_engine() -> FailoverEngine:
    global _failover_engine
    if _failover_engine is None:
        with _lock:
            if _failover_engine is None:
                _failover_engine = FailoverEngine()
    return _failover_engine


def get_llm_routing_facade() -> LLMRoutingFacade:
    global _facade
    if _facade is None:
        with _lock:
            if _facade is None:
                _facade = LLMRoutingFacade(
                    smart=get_smart_router(),
                    scenario=get_scenario_router(),
                    failover=get_failover_engine(),
                )
    return _facade
