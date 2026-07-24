"""W2-AK · Data Connection 安全治理引擎（#125 #126 #127）."""
from __future__ import annotations

import ipaddress
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

_MAX_EXECUTION_POLICIES = 200
_MAX_EGRESS_POLICIES = 200
_MAX_EXPORTABLE_MARKING_POLICIES = 200
_MAX_ATTEMPTS_PER_POLICY = 200
_MAX_EGRESS_EVALS = 200
_MAX_MARKING_EVALS = 200


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DataConnectionSecurityError(Exception):
    """安全治理错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #125 Webhook Execution Policy ════════════════════

class WebhookExecutionPolicy(BaseModel):
    policy_id: str = ""
    name: str
    webhook_id: str
    max_concurrent: int = 5
    rate_limit_per_minute: int = 60
    timeout_ms: int = 30000
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    retry_on_status: list[int] = [429, 500, 502, 503, 504]
    circuit_breaker_enabled: bool = True
    circuit_failure_threshold: float = 0.5
    circuit_cooldown_ms: int = 60000
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


class ExecutionState(BaseModel):
    state_id: str = ""
    policy_id: str
    current_concurrent: int = 0
    window_start: str = ""
    window_count: int = 0
    circuit_state: str = "closed"
    circuit_failure_count: int = 0
    circuit_total_count: int = 0
    circuit_opened_at: str | None = None


class ExecutionAttempt(BaseModel):
    attempt_id: str = ""
    policy_id: str
    webhook_call_id: str
    attempt_number: int = 1
    status: str = "pending"
    http_status: int | None = None
    duration_ms: int = 0
    started_at: str = ""
    finished_at: str | None = None
    error_message: str | None = None
    next_attempt_at: str | None = None


class WebhookExecutionPolicyEngine:
    """Webhook 执行策略引擎（并发控制 + 速率限制 + 重试 + 熔断）."""

    _instance: WebhookExecutionPolicyEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._policies: dict[str, WebhookExecutionPolicy] = {}
        self._states: dict[str, ExecutionState] = {}
        self._attempts: dict[str, deque[ExecutionAttempt]] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> WebhookExecutionPolicyEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _new_state(self, policy_id: str) -> ExecutionState:
        return ExecutionState(
            state_id=f"es-{uuid.uuid4().hex[:8]}",
            policy_id=policy_id,
            window_start=_now_iso(),
        )

    # ── CRUD ──

    def register(self, policy: WebhookExecutionPolicy) -> WebhookExecutionPolicy:
        if not policy.name or not policy.name.strip():
            raise DataConnectionSecurityError("MISSING_NAME", "policy name is required")
        if not policy.webhook_id or not policy.webhook_id.strip():
            raise DataConnectionSecurityError("MISSING_WEBHOOK", "webhook_id is required")
        if policy.max_concurrent <= 0:
            raise DataConnectionSecurityError("INVALID_CONCURRENCY", "max_concurrent must be positive")
        if policy.rate_limit_per_minute <= 0:
            raise DataConnectionSecurityError("INVALID_RATE_LIMIT", "rate_limit_per_minute must be positive")
        if policy.timeout_ms <= 0:
            raise DataConnectionSecurityError("INVALID_TIMEOUT", "timeout_ms must be positive")
        if policy.max_retries < 0:
            raise DataConnectionSecurityError("INVALID_RETRY_COUNT", "max_retries must be non-negative")
        if not 0 < policy.circuit_failure_threshold <= 1:
            raise DataConnectionSecurityError("INVALID_THRESHOLD", "failure threshold must be in (0, 1]")

        now = _now_iso()
        pid = f"wep-{uuid.uuid4().hex[:8]}"
        p = policy.model_copy(update={"policy_id": pid, "created_at": now, "updated_at": now})
        with self._lock:
            if len(self._policies) >= _MAX_EXECUTION_POLICIES:
                oldest = min(self._policies.values(), key=lambda x: x.created_at)
                del self._policies[oldest.policy_id]
                self._states.pop(oldest.policy_id, None)
                self._attempts.pop(oldest.policy_id, None)
            self._policies[pid] = p
            self._states[pid] = self._new_state(pid)
            self._attempts[pid] = deque(maxlen=_MAX_ATTEMPTS_PER_POLICY)
        return p

    def get(self, policy_id: str) -> WebhookExecutionPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
        if p is None:
            raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
        return p

    def list(self, webhook_id: str | None = None, status: str | None = None) -> list[WebhookExecutionPolicy]:
        with self._lock:
            results = list(self._policies.values())
        if webhook_id:
            results = [p for p in results if p.webhook_id == webhook_id]
        if status:
            results = [p for p in results if p.status == status]
        return results

    def update(self, policy_id: str, updates: dict) -> WebhookExecutionPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            data = p.model_dump()
            data.update(updates)
            updated = WebhookExecutionPolicy(**{**data, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def delete(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                self._states.pop(policy_id, None)
                self._attempts.pop(policy_id, None)
                return True
        return False

    # ── 执行控制 ──

    def acquire_slot(self, policy_id: str, call_id: str) -> ExecutionAttempt:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            state = self._states.get(policy_id)
            if state is None:
                state = self._new_state(policy_id)
                self._states[policy_id] = state

            if p.circuit_breaker_enabled and state.circuit_state == "open":
                if state.circuit_opened_at:
                    opened = datetime.fromisoformat(state.circuit_opened_at)
                    elapsed_ms = (datetime.now(timezone.utc) - opened).total_seconds() * 1000
                    if elapsed_ms >= p.circuit_cooldown_ms:
                        state.circuit_state = "half_open"
                    else:
                        raise DataConnectionSecurityError("CIRCUIT_OPEN", "circuit breaker is open")
                else:
                    raise DataConnectionSecurityError("CIRCUIT_OPEN", "circuit breaker is open")

            now = datetime.now(timezone.utc)
            window_start_dt = datetime.fromisoformat(state.window_start)
            if (now - window_start_dt).total_seconds() >= 60:
                state.window_start = _now_iso()
                state.window_count = 0

            if state.current_concurrent >= p.max_concurrent:
                raise DataConnectionSecurityError("CONCURRENCY_EXCEEDED", "max concurrent requests exceeded")
            if state.window_count >= p.rate_limit_per_minute:
                raise DataConnectionSecurityError("RATE_LIMIT_EXCEEDED", "rate limit exceeded")

            state.current_concurrent += 1
            state.window_count += 1

            attempt = ExecutionAttempt(
                attempt_id=f"eat-{uuid.uuid4().hex[:8]}",
                policy_id=policy_id,
                webhook_call_id=call_id,
                attempt_number=1,
                status="pending",
                started_at=_now_iso(),
            )
            if policy_id not in self._attempts:
                self._attempts[policy_id] = deque(maxlen=_MAX_ATTEMPTS_PER_POLICY)
            self._attempts[policy_id].append(attempt)
        return attempt

    def release_slot(self, policy_id: str, call_id: str, success: bool,
                     http_status: int | None, duration_ms: int,
                     error_message: str | None = None) -> ExecutionAttempt:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            state = self._states.get(policy_id)
            if state is None:
                state = self._new_state(policy_id)
                self._states[policy_id] = state

            if state.current_concurrent > 0:
                state.current_concurrent -= 1

            attempts = self._attempts.get(policy_id, deque())
            target = None
            for a in reversed(attempts):
                if a.webhook_call_id == call_id and a.status == "pending":
                    target = a
                    break
            if target is None:
                target = ExecutionAttempt(
                    attempt_id=f"eat-{uuid.uuid4().hex[:8]}",
                    policy_id=policy_id,
                    webhook_call_id=call_id,
                    status="success" if success else "failed",
                    http_status=http_status,
                    duration_ms=duration_ms,
                    started_at=_now_iso(),
                    finished_at=_now_iso(),
                    error_message=error_message,
                )
                attempts.append(target)
            else:
                target.status = "success" if success else "failed"
                target.http_status = http_status
                target.duration_ms = duration_ms
                target.finished_at = _now_iso()
                target.error_message = error_message

            if p.circuit_breaker_enabled:
                self._update_circuit_nolock(state, p, success)
        return target

    def _update_circuit_nolock(self, state: ExecutionState, policy: WebhookExecutionPolicy, success: bool) -> None:
        if state.circuit_state == "half_open":
            if success:
                state.circuit_state = "closed"
                state.circuit_failure_count = 0
                state.circuit_total_count = 0
                state.circuit_opened_at = None
            else:
                state.circuit_state = "open"
                state.circuit_opened_at = _now_iso()
            return

        state.circuit_total_count += 1
        if not success:
            state.circuit_failure_count += 1

        if state.circuit_total_count >= 5:
            failure_rate = state.circuit_failure_count / state.circuit_total_count
            if failure_rate >= policy.circuit_failure_threshold:
                state.circuit_state = "open"
                state.circuit_opened_at = _now_iso()

    def record_retry(self, policy_id: str, call_id: str, attempt_number: int,
                     next_attempt_at: str, error_message: str | None = None) -> ExecutionAttempt:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            if attempt_number > p.max_retries + 1:
                raise DataConnectionSecurityError("INVALID_RETRY_COUNT", "retries exceeded max_retries")

            attempts = self._attempts.get(policy_id, deque())
            target = None
            for a in reversed(attempts):
                if a.webhook_call_id == call_id:
                    target = a
                    break
            if target is None:
                target = ExecutionAttempt(
                    attempt_id=f"eat-{uuid.uuid4().hex[:8]}",
                    policy_id=policy_id,
                    webhook_call_id=call_id,
                    attempt_number=attempt_number,
                    status="pending",
                    started_at=_now_iso(),
                    error_message=error_message,
                    next_attempt_at=next_attempt_at,
                )
                attempts.append(target)
            else:
                target.attempt_number = attempt_number
                target.status = "pending"
                target.error_message = error_message
                target.next_attempt_at = next_attempt_at
        return target

    def get_execution_state(self, policy_id: str) -> ExecutionState:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            state = self._states.get(policy_id)
            if state is None:
                state = self._new_state(policy_id)
                self._states[policy_id] = state
        return state

    def reset_state(self, policy_id: str) -> ExecutionState:
        with self._lock:
            if policy_id not in self._policies:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            state = self._new_state(policy_id)
            self._states[policy_id] = state
        return state

    def list_attempts(self, policy_id: str, limit: int = 50) -> list[ExecutionAttempt]:
        with self._lock:
            attempts = self._attempts.get(policy_id, deque())
            results = list(attempts)[-limit:]
        return list(reversed(results))

    # ── 熔断控制 ──

    def trip_circuit(self, policy_id: str) -> ExecutionState:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            state = self._states.get(policy_id)
            if state is None:
                state = self._new_state(policy_id)
                self._states[policy_id] = state
            state.circuit_state = "open"
            state.circuit_opened_at = _now_iso()
        return state

    def reset_circuit(self, policy_id: str) -> ExecutionState:
        with self._lock:
            if policy_id not in self._policies:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            state = self._states.get(policy_id)
            if state is None:
                state = self._new_state(policy_id)
                self._states[policy_id] = state
            state.circuit_state = "closed"
            state.circuit_failure_count = 0
            state.circuit_total_count = 0
            state.circuit_opened_at = None
        return state


_execution_policy_engine: WebhookExecutionPolicyEngine | None = None
_execution_policy_engine_lock = threading.Lock()


def get_webhook_execution_policy_engine() -> WebhookExecutionPolicyEngine:
    global _execution_policy_engine
    if _execution_policy_engine is None:
        with _execution_policy_engine_lock:
            if _execution_policy_engine is None:
                _execution_policy_engine = WebhookExecutionPolicyEngine.get_instance()
    return _execution_policy_engine


# ════════════════════ #126 Egress Policy ════════════════════

class EgressPolicy(BaseModel):
    policy_id: str = ""
    name: str
    description: str | None = None
    effect: str = "allow"
    cidr_blocks: list[str] = []
    ports: list[int] = []
    domains: list[str] = []
    protocols: list[str] = []
    priority: int = 100
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


class EgressEvaluation(BaseModel):
    eval_id: str = ""
    policy_id: str | None = None
    destination: str
    port: int
    protocol: str
    decision: str
    matched_rules: list[str] = []
    reason: str = ""
    evaluated_at: str = ""


_VALID_EGRESS_EFFECTS = {"allow", "deny"}
_VALID_PROTOCOLS = {"http", "https", "tcp", "udp"}


def _is_valid_cidr(cidr: str) -> bool:
    try:
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False


def _cidr_contains(cidr: str, ip_str: str) -> bool:
    try:
        net = ipaddress.ip_network(cidr, strict=False)
        ip = ipaddress.ip_address(ip_str)
        return ip in net
    except ValueError:
        return False


def _domain_matches(pattern: str, domain: str) -> bool:
    pattern = pattern.lower()
    domain = domain.lower()
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return domain.endswith(suffix) or domain == pattern[2:]
    return pattern == domain


def _is_ip_address(dest: str) -> bool:
    try:
        ipaddress.ip_address(dest)
        return True
    except ValueError:
        return False


class EgressPolicyEngine:
    """出站策略引擎（CIDR/端口/域名/协议 白名单+黑名单）."""

    _instance: EgressPolicyEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._policies: dict[str, EgressPolicy] = {}
        self._evals: deque[EgressEvaluation] = deque(maxlen=_MAX_EGRESS_EVALS)
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> EgressPolicyEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── CRUD ──

    def register(self, policy: EgressPolicy) -> EgressPolicy:
        if not policy.name or not policy.name.strip():
            raise DataConnectionSecurityError("MISSING_NAME", "policy name is required")
        if policy.effect not in _VALID_EGRESS_EFFECTS:
            raise DataConnectionSecurityError("INVALID_EFFECT", f"effect must be one of {_VALID_EGRESS_EFFECTS}")
        if not any([policy.cidr_blocks, policy.ports, policy.domains, policy.protocols]):
            raise DataConnectionSecurityError("EMPTY_RULES", "at least one rule type must be specified")
        if policy.priority <= 0:
            raise DataConnectionSecurityError("INVALID_PRIORITY", "priority must be positive")
        for cidr in policy.cidr_blocks:
            if not _is_valid_cidr(cidr):
                raise DataConnectionSecurityError("INVALID_CIDR", f"invalid CIDR: {cidr}")
        for port in policy.ports:
            if not (1 <= port <= 65535):
                raise DataConnectionSecurityError("INVALID_PORT", f"invalid port: {port}")
        for proto in policy.protocols:
            if proto not in _VALID_PROTOCOLS:
                raise DataConnectionSecurityError("INVALID_PROTOCOL", f"invalid protocol: {proto}")

        now = _now_iso()
        pid = f"egp-{uuid.uuid4().hex[:8]}"
        p = policy.model_copy(update={"policy_id": pid, "created_at": now, "updated_at": now})
        with self._lock:
            if len(self._policies) >= _MAX_EGRESS_POLICIES:
                oldest = min(self._policies.values(), key=lambda x: x.created_at)
                del self._policies[oldest.policy_id]
            self._policies[pid] = p
        return p

    def get(self, policy_id: str) -> EgressPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
        if p is None:
            raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
        return p

    def list(self, effect: str | None = None, status: str | None = None) -> list[EgressPolicy]:
        with self._lock:
            results = list(self._policies.values())
        if effect:
            results = [p for p in results if p.effect == effect]
        if status:
            results = [p for p in results if p.status == status]
        return sorted(results, key=lambda p: p.priority)

    def update(self, policy_id: str, updates: dict) -> EgressPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            data = p.model_dump()
            data.update(updates)
            updated = EgressPolicy(**{**data, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def delete(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
        return False

    # ── 评估 ──

    def _match_policy(self, policy: EgressPolicy, destination: str, port: int, protocol: str) -> list[str]:
        matched: list[str] = []
        dest_is_ip = _is_ip_address(destination)

        if policy.cidr_blocks:
            if dest_is_ip:
                if any(_cidr_contains(cidr, destination) for cidr in policy.cidr_blocks):
                    matched.append("cidr")
                else:
                    return []
            else:
                return []

        if policy.ports:
            if port not in policy.ports:
                return []
            matched.append("port")

        if policy.domains:
            if not dest_is_ip:
                if any(_domain_matches(d, destination) for d in policy.domains):
                    matched.append("domain")
            else:
                return []

        if policy.protocols:
            if protocol not in policy.protocols:
                return []
            matched.append("protocol")

        return matched

    def evaluate(self, destination: str, port: int, protocol: str,
                 source_context: dict | None = None) -> EgressEvaluation:
        with self._lock:
            policies = sorted(self._policies.values(), key=lambda p: p.priority)
        active = [p for p in policies if p.status == "active"]

        matched_policy = None
        matched_rules: list[str] = []
        for p in active:
            rules = self._match_policy(p, destination, port, protocol)
            if rules:
                matched_policy = p
                matched_rules = rules
                break

        if matched_policy:
            decision = "allowed" if matched_policy.effect == "allow" else "denied"
            reason = f"matched policy {matched_policy.name} ({matched_policy.effect})"
            eval_result = EgressEvaluation(
                eval_id=f"ege-{uuid.uuid4().hex[:8]}",
                policy_id=matched_policy.policy_id,
                destination=destination,
                port=port,
                protocol=protocol,
                decision=decision,
                matched_rules=matched_rules,
                reason=reason,
                evaluated_at=_now_iso(),
            )
        else:
            eval_result = EgressEvaluation(
                eval_id=f"ege-{uuid.uuid4().hex[:8]}",
                policy_id=None,
                destination=destination,
                port=port,
                protocol=protocol,
                decision="denied",
                matched_rules=[],
                reason="no matching policy, default deny",
                evaluated_at=_now_iso(),
            )

        with self._lock:
            self._evals.append(eval_result)
        return eval_result

    def evaluate_batch(self, requests: list[dict]) -> list[EgressEvaluation]:
        results = []
        for req in requests:
            results.append(self.evaluate(
                destination=req["destination"],
                port=req.get("port", 0),
                protocol=req.get("protocol", "tcp"),
                source_context=req.get("source_context"),
            ))
        return results

    def check_allowed(self, destination: str, port: int, protocol: str) -> bool:
        return self.evaluate(destination, port, protocol).decision == "allowed"

    def list_evaluations(self, policy_id: str | None = None, limit: int = 50) -> list[EgressEvaluation]:
        with self._lock:
            results = list(self._evals)
        if policy_id:
            results = [e for e in results if e.policy_id == policy_id]
        return list(reversed(results))[-limit:]

    # ── 工具 ──

    def add_cidr(self, policy_id: str, cidr: str) -> EgressPolicy:
        if not _is_valid_cidr(cidr):
            raise DataConnectionSecurityError("INVALID_CIDR", f"invalid CIDR: {cidr}")
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            new_cidrs = list(p.cidr_blocks)
            if cidr not in new_cidrs:
                new_cidrs.append(cidr)
            updated = p.model_copy(update={"cidr_blocks": new_cidrs, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def remove_cidr(self, policy_id: str, cidr: str) -> EgressPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            new_cidrs = [c for c in p.cidr_blocks if c != cidr]
            updated = p.model_copy(update={"cidr_blocks": new_cidrs, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def add_domain(self, policy_id: str, domain: str) -> EgressPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            new_domains = list(p.domains)
            if domain not in new_domains:
                new_domains.append(domain)
            updated = p.model_copy(update={"domains": new_domains, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def remove_domain(self, policy_id: str, domain: str) -> EgressPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            new_domains = [d for d in p.domains if d != domain]
            updated = p.model_copy(update={"domains": new_domains, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated


_egress_policy_engine: EgressPolicyEngine | None = None
_egress_policy_engine_lock = threading.Lock()


def get_egress_policy_engine() -> EgressPolicyEngine:
    global _egress_policy_engine
    if _egress_policy_engine is None:
        with _egress_policy_engine_lock:
            if _egress_policy_engine is None:
                _egress_policy_engine = EgressPolicyEngine.get_instance()
    return _egress_policy_engine


# ════════════════════ #127 Exportable Marking ════════════════════

class ExportableMarkingPolicy(BaseModel):
    policy_id: str = ""
    name: str
    connection_id: str
    marking_level: str = "internal"
    export_action: str = "deny"
    mask_character: str = "*"
    redact_text: str = "[REDACTED]"
    affected_columns: list[str] = []
    affected_markings: list[str] = []
    priority: int = 100
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


class MarkingEvaluation(BaseModel):
    eval_id: str = ""
    policy_id: str | None = None
    connection_id: str
    column_name: str | None = None
    markings: list[str] = []
    decision: str
    masked_value: str | None = None
    reason: str = ""
    evaluated_at: str = ""


_VALID_MARKING_LEVELS = {"public", "internal", "restricted", "confidential"}
_VALID_EXPORT_ACTIONS = {"allow", "deny", "mask", "redact"}


class ExportableMarkingEngine:
    """可导出标记控制引擎（标记级别驱动导出权限+掩码/替换）."""

    _instance: ExportableMarkingEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._policies: dict[str, ExportableMarkingPolicy] = {}
        self._evals: deque[MarkingEvaluation] = deque(maxlen=_MAX_MARKING_EVALS)
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ExportableMarkingEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── CRUD ──

    def register(self, policy: ExportableMarkingPolicy) -> ExportableMarkingPolicy:
        if not policy.name or not policy.name.strip():
            raise DataConnectionSecurityError("MISSING_NAME", "policy name is required")
        if not policy.connection_id or not policy.connection_id.strip():
            raise DataConnectionSecurityError("MISSING_CONNECTION", "connection_id is required")
        if policy.marking_level not in _VALID_MARKING_LEVELS:
            raise DataConnectionSecurityError("INVALID_MARKING_LEVEL",
                                              f"marking_level must be one of {_VALID_MARKING_LEVELS}")
        if policy.export_action not in _VALID_EXPORT_ACTIONS:
            raise DataConnectionSecurityError("INVALID_EXPORT_ACTION",
                                              f"export_action must be one of {_VALID_EXPORT_ACTIONS}")
        if policy.priority <= 0:
            raise DataConnectionSecurityError("INVALID_PRIORITY", "priority must be positive")

        now = _now_iso()
        pid = f"emp-{uuid.uuid4().hex[:8]}"
        p = policy.model_copy(update={"policy_id": pid, "created_at": now, "updated_at": now})
        with self._lock:
            if len(self._policies) >= _MAX_EXPORTABLE_MARKING_POLICIES:
                oldest = min(self._policies.values(), key=lambda x: x.created_at)
                del self._policies[oldest.policy_id]
            self._policies[pid] = p
        return p

    def get(self, policy_id: str) -> ExportableMarkingPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
        if p is None:
            raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
        return p

    def list(self, connection_id: str | None = None, status: str | None = None,
             marking_level: str | None = None) -> list[ExportableMarkingPolicy]:
        with self._lock:
            results = list(self._policies.values())
        if connection_id:
            results = [p for p in results if p.connection_id == connection_id]
        if status:
            results = [p for p in results if p.status == status]
        if marking_level:
            results = [p for p in results if p.marking_level == marking_level]
        return sorted(results, key=lambda p: p.priority)

    def update(self, policy_id: str, updates: dict) -> ExportableMarkingPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            data = p.model_dump()
            data.update(updates)
            updated = ExportableMarkingPolicy(**{**data, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def delete(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
        return False

    # ── 评估 ──

    def _level_rank(self, level: str) -> int:
        ranks = {"public": 0, "internal": 1, "restricted": 2, "confidential": 3}
        return ranks.get(level, 0)

    def evaluate(self, connection_id: str, column_name: str | None,
                 markings: list[str], value: str | None = None) -> MarkingEvaluation:
        with self._lock:
            policies = sorted(self._policies.values(), key=lambda p: p.priority)
        active = [p for p in policies if p.status == "active" and p.connection_id == connection_id]

        matched_policy = None
        for p in active:
            if p.affected_columns and column_name and column_name not in p.affected_columns:
                continue
            if p.affected_markings:
                if not any(m in markings for m in p.affected_markings):
                    continue
            matched_policy = p
            break

        if matched_policy:
            action = matched_policy.export_action
            masked_value = None
            if action == "allow":
                decision = "allowed"
            elif action == "deny":
                decision = "denied"
            elif action == "mask":
                decision = "masked"
                if value is not None:
                    masked_value = matched_policy.mask_character * len(value)
            elif action == "redact":
                decision = "redacted"
                masked_value = matched_policy.redact_text
            else:
                decision = "denied"

            reason = f"matched policy {matched_policy.name} (action={action})"
            result = MarkingEvaluation(
                eval_id=f"mke-{uuid.uuid4().hex[:8]}",
                policy_id=matched_policy.policy_id,
                connection_id=connection_id,
                column_name=column_name,
                markings=markings,
                decision=decision,
                masked_value=masked_value,
                reason=reason,
                evaluated_at=_now_iso(),
            )
        else:
            result = MarkingEvaluation(
                eval_id=f"mke-{uuid.uuid4().hex[:8]}",
                policy_id=None,
                connection_id=connection_id,
                column_name=column_name,
                markings=markings,
                decision="allowed",
                masked_value=value,
                reason="no matching policy, default allow",
                evaluated_at=_now_iso(),
            )

        with self._lock:
            self._evals.append(result)
        return result

    def evaluate_row(self, connection_id: str, columns: list[dict]) -> list[MarkingEvaluation]:
        results = []
        for col in columns:
            results.append(self.evaluate(
                connection_id=connection_id,
                column_name=col.get("name"),
                markings=col.get("markings", []),
                value=col.get("value"),
            ))
        return results

    def can_export(self, connection_id: str, markings: list[str]) -> bool:
        result = self.evaluate(connection_id, None, markings)
        return result.decision in ("allowed", "masked", "redacted")

    def list_evaluations(self, policy_id: str | None = None, limit: int = 50) -> list[MarkingEvaluation]:
        with self._lock:
            results = list(self._evals)
        if policy_id:
            results = [e for e in results if e.policy_id == policy_id]
        return list(reversed(results))[-limit:]

    # ── 工具 ──

    def add_affected_column(self, policy_id: str, column: str) -> ExportableMarkingPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            new_cols = list(p.affected_columns)
            if column not in new_cols:
                new_cols.append(column)
            updated = p.model_copy(update={"affected_columns": new_cols, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def remove_affected_column(self, policy_id: str, column: str) -> ExportableMarkingPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            new_cols = [c for c in p.affected_columns if c != column]
            updated = p.model_copy(update={"affected_columns": new_cols, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def add_affected_marking(self, policy_id: str, marking: str) -> ExportableMarkingPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            new_markings = list(p.affected_markings)
            if marking not in new_markings:
                new_markings.append(marking)
            updated = p.model_copy(update={"affected_markings": new_markings, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated

    def remove_affected_marking(self, policy_id: str, marking: str) -> ExportableMarkingPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                raise DataConnectionSecurityError("NOT_FOUND", f"policy {policy_id} not found")
            new_markings = [m for m in p.affected_markings if m != marking]
            updated = p.model_copy(update={"affected_markings": new_markings, "updated_at": _now_iso()})
            self._policies[policy_id] = updated
        return updated


_exportable_marking_engine: ExportableMarkingEngine | None = None
_exportable_marking_engine_lock = threading.Lock()


def get_exportable_marking_engine() -> ExportableMarkingEngine:
    global _exportable_marking_engine
    if _exportable_marking_engine is None:
        with _exportable_marking_engine_lock:
            if _exportable_marking_engine is None:
                _exportable_marking_engine = ExportableMarkingEngine.get_instance()
    return _exportable_marking_engine
