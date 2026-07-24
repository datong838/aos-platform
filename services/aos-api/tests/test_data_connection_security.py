"""W2-AK · Data Connection 安全治理组测试（#125 / #126 / #127）."""
from __future__ import annotations

import threading

import pytest

from aos_api.data_connection_security import (
    DataConnectionSecurityError,
    EgressPolicy,
    EgressPolicyEngine,
    ExportableMarkingEngine,
    ExportableMarkingPolicy,
    WebhookExecutionPolicy,
    WebhookExecutionPolicyEngine,
    get_egress_policy_engine,
    get_exportable_marking_engine,
    get_webhook_execution_policy_engine,
)


# ════════════════════ WebhookExecutionPolicyEngine ════════════════════

class TestWebhookExecutionPolicy:
    def setup_method(self) -> None:
        self.eng = WebhookExecutionPolicyEngine.__new__(WebhookExecutionPolicyEngine)
        self.eng._policies = {}
        self.eng._states = {}
        self.eng._attempts = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> WebhookExecutionPolicy:
        defaults: dict[str, object] = {
            "name": "test-policy",
            "webhook_id": "wh-1",
            "max_concurrent": 3,
            "rate_limit_per_minute": 10,
            "timeout_ms": 5000,
            "max_retries": 2,
        }
        defaults.update(kw)
        return WebhookExecutionPolicy(**defaults)

    def test_register_returns_with_id(self) -> None:
        p = self.eng.register(self._mk())
        assert p.policy_id.startswith("wep-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_missing_webhook(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(webhook_id=""))
        assert exc.value.code == "MISSING_WEBHOOK"

    def test_register_invalid_concurrency(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(max_concurrent=0))
        assert exc.value.code == "INVALID_CONCURRENCY"

    def test_register_invalid_rate_limit(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(rate_limit_per_minute=-1))
        assert exc.value.code == "INVALID_RATE_LIMIT"

    def test_register_invalid_threshold(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(circuit_failure_threshold=1.5))
        assert exc.value.code == "INVALID_THRESHOLD"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_filter_webhook_id(self) -> None:
        self.eng.register(self._mk(name="a", webhook_id="wh-1"))
        self.eng.register(self._mk(name="b", webhook_id="wh-2"))
        assert len(self.eng.list(webhook_id="wh-1")) == 1

    def test_update(self) -> None:
        p = self.eng.register(self._mk())
        updated = self.eng.update(p.policy_id, {"name": "new-name", "max_concurrent": 10})
        assert updated.name == "new-name"
        assert updated.max_concurrent == 10

    def test_delete(self) -> None:
        p = self.eng.register(self._mk())
        assert self.eng.delete(p.policy_id) is True
        assert self.eng.delete(p.policy_id) is False

    def test_acquire_slot_success(self) -> None:
        p = self.eng.register(self._mk())
        attempt = self.eng.acquire_slot(p.policy_id, "call-1")
        assert attempt.status == "pending"
        assert attempt.attempt_number == 1
        state = self.eng.get_execution_state(p.policy_id)
        assert state.current_concurrent == 1
        assert state.window_count == 1

    def test_acquire_slot_concurrency_exceeded(self) -> None:
        p = self.eng.register(self._mk(max_concurrent=1))
        self.eng.acquire_slot(p.policy_id, "call-1")
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.acquire_slot(p.policy_id, "call-2")
        assert exc.value.code == "CONCURRENCY_EXCEEDED"

    def test_release_slot_success(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.acquire_slot(p.policy_id, "call-1")
        attempt = self.eng.release_slot(p.policy_id, "call-1", True, 200, 100)
        assert attempt.status == "success"
        state = self.eng.get_execution_state(p.policy_id)
        assert state.current_concurrent == 0

    def test_release_slot_failure(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.acquire_slot(p.policy_id, "call-1")
        attempt = self.eng.release_slot(p.policy_id, "call-1", False, 500, 200, "error")
        assert attempt.status == "failed"
        assert attempt.error_message == "error"

    def test_record_retry(self) -> None:
        p = self.eng.register(self._mk())
        from aos_api.data_connection_security import _now_iso
        next_time = _now_iso()
        attempt = self.eng.record_retry(p.policy_id, "call-1", 2, next_time, "timeout")
        assert attempt.attempt_number == 2
        assert attempt.next_attempt_at == next_time

    def test_get_execution_state(self) -> None:
        p = self.eng.register(self._mk())
        state = self.eng.get_execution_state(p.policy_id)
        assert state.policy_id == p.policy_id
        assert state.circuit_state == "closed"

    def test_reset_state(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.acquire_slot(p.policy_id, "call-1")
        state = self.eng.reset_state(p.policy_id)
        assert state.current_concurrent == 0
        assert state.window_count == 0

    def test_trip_circuit(self) -> None:
        p = self.eng.register(self._mk())
        state = self.eng.trip_circuit(p.policy_id)
        assert state.circuit_state == "open"
        assert state.circuit_opened_at is not None

    def test_circuit_open_rejects_acquire(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.trip_circuit(p.policy_id)
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.acquire_slot(p.policy_id, "call-1")
        assert exc.value.code == "CIRCUIT_OPEN"

    def test_reset_circuit(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.trip_circuit(p.policy_id)
        state = self.eng.reset_circuit(p.policy_id)
        assert state.circuit_state == "closed"
        assert state.circuit_failure_count == 0

    def test_list_attempts_reverse_order(self) -> None:
        p = self.eng.register(self._mk())
        for i in range(5):
            self.eng.acquire_slot(p.policy_id, f"call-{i}")
            self.eng.release_slot(p.policy_id, f"call-{i}", True, 200, 100)
        attempts = self.eng.list_attempts(p.policy_id)
        assert len(attempts) >= 5

    def test_max_policies_eviction(self) -> None:
        from aos_api.data_connection_security import _MAX_EXECUTION_POLICIES
        for i in range(_MAX_EXECUTION_POLICIES + 5):
            self.eng.register(WebhookExecutionPolicy(name=f"p-{i}", webhook_id=f"w-{i}"))
        assert len(self.eng._policies) == _MAX_EXECUTION_POLICIES


# ════════════════════ EgressPolicyEngine ════════════════════

class TestEgressPolicy:
    def setup_method(self) -> None:
        self.eng = EgressPolicyEngine.__new__(EgressPolicyEngine)
        self.eng._policies = {}
        self.eng._evals = __import__("collections").deque(maxlen=200)
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> EgressPolicy:
        defaults: dict[str, object] = {
            "name": "test-policy",
            "effect": "allow",
            "cidr_blocks": ["192.168.1.0/24"],
            "ports": [443],
            "domains": [],
            "protocols": ["https"],
            "priority": 100,
        }
        defaults.update(kw)
        return EgressPolicy(**defaults)

    def test_register_returns_with_id(self) -> None:
        p = self.eng.register(self._mk())
        assert p.policy_id.startswith("egp-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_empty_rules(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(cidr_blocks=[], ports=[], domains=[], protocols=[]))
        assert exc.value.code == "EMPTY_RULES"

    def test_register_invalid_cidr(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(cidr_blocks=["not-a-cidr"]))
        assert exc.value.code == "INVALID_CIDR"

    def test_register_invalid_port(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(ports=[99999]))
        assert exc.value.code == "INVALID_PORT"

    def test_register_invalid_protocol(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(protocols=["ftp"]))
        assert exc.value.code == "INVALID_PROTOCOL"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_sorted_by_priority(self) -> None:
        self.eng.register(self._mk(name="low", priority=200))
        self.eng.register(self._mk(name="high", priority=10))
        results = self.eng.list()
        assert results[0].priority <= results[1].priority

    def test_update(self) -> None:
        p = self.eng.register(self._mk())
        updated = self.eng.update(p.policy_id, {"name": "new-name", "priority": 50})
        assert updated.name == "new-name"
        assert updated.priority == 50

    def test_delete(self) -> None:
        p = self.eng.register(self._mk())
        assert self.eng.delete(p.policy_id) is True
        assert self.eng.delete(p.policy_id) is False

    def test_evaluate_cidr_match_allow(self) -> None:
        p = self.eng.register(self._mk(effect="allow"))
        result = self.eng.evaluate("192.168.1.100", 443, "https")
        assert result.decision == "allowed"
        assert result.policy_id == p.policy_id
        assert "cidr" in result.matched_rules

    def test_evaluate_cidr_no_match_default_deny(self) -> None:
        self.eng.register(self._mk(effect="allow"))
        result = self.eng.evaluate("10.0.0.1", 443, "https")
        assert result.decision == "denied"
        assert result.policy_id is None

    def test_evaluate_port_mismatch(self) -> None:
        self.eng.register(self._mk())
        result = self.eng.evaluate("192.168.1.100", 80, "https")
        assert result.decision == "denied"

    def test_evaluate_domain_wildcard(self) -> None:
        self.eng.register(self._mk(
            cidr_blocks=[],
            domains=["*.example.com"],
            ports=[443],
            protocols=["https"],
        ))
        result = self.eng.evaluate("api.example.com", 443, "https")
        assert result.decision == "allowed"
        assert "domain" in result.matched_rules

    def test_evaluate_priority_order(self) -> None:
        self.eng.register(self._mk(name="deny-high", effect="deny", priority=10))
        self.eng.register(self._mk(name="allow-low", effect="allow", priority=100))
        result = self.eng.evaluate("192.168.1.100", 443, "https")
        assert result.decision == "denied"

    def test_evaluate_batch(self) -> None:
        self.eng.register(self._mk())
        results = self.eng.evaluate_batch([
            {"destination": "192.168.1.1", "port": 443, "protocol": "https"},
            {"destination": "10.0.0.1", "port": 80, "protocol": "http"},
        ])
        assert len(results) == 2
        assert results[0].decision == "allowed"
        assert results[1].decision == "denied"

    def test_check_allowed(self) -> None:
        self.eng.register(self._mk())
        assert self.eng.check_allowed("192.168.1.1", 443, "https") is True
        assert self.eng.check_allowed("10.0.0.1", 443, "https") is False

    def test_add_remove_cidr(self) -> None:
        p = self.eng.register(self._mk(cidr_blocks=["10.0.0.0/8"]))
        updated = self.eng.add_cidr(p.policy_id, "192.168.0.0/16")
        assert "192.168.0.0/16" in updated.cidr_blocks
        updated2 = self.eng.remove_cidr(p.policy_id, "10.0.0.0/8")
        assert "10.0.0.0/8" not in updated2.cidr_blocks

    def test_add_remove_domain(self) -> None:
        p = self.eng.register(self._mk(cidr_blocks=[], domains=["example.com"], ports=[443], protocols=["https"]))
        updated = self.eng.add_domain(p.policy_id, "api.example.com")
        assert "api.example.com" in updated.domains
        updated2 = self.eng.remove_domain(p.policy_id, "example.com")
        assert "example.com" not in updated2.domains

    def test_list_evaluations(self) -> None:
        self.eng.register(self._mk())
        self.eng.evaluate("192.168.1.1", 443, "https")
        self.eng.evaluate("10.0.0.1", 443, "https")
        evals = self.eng.list_evaluations()
        assert len(evals) == 2

    def test_max_policies_eviction(self) -> None:
        from aos_api.data_connection_security import _MAX_EGRESS_POLICIES
        for i in range(_MAX_EGRESS_POLICIES + 5):
            self.eng.register(EgressPolicy(name=f"p-{i}", cidr_blocks=[f"10.{i}.0.0/16"]))
        assert len(self.eng._policies) == _MAX_EGRESS_POLICIES


# ════════════════════ ExportableMarkingEngine ════════════════════

class TestExportableMarking:
    def setup_method(self) -> None:
        self.eng = ExportableMarkingEngine.__new__(ExportableMarkingEngine)
        self.eng._policies = {}
        self.eng._evals = __import__("collections").deque(maxlen=200)
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> ExportableMarkingPolicy:
        defaults: dict[str, object] = {
            "name": "test-policy",
            "connection_id": "conn-1",
            "marking_level": "restricted",
            "export_action": "deny",
            "priority": 100,
        }
        defaults.update(kw)
        return ExportableMarkingPolicy(**defaults)

    def test_register_returns_with_id(self) -> None:
        p = self.eng.register(self._mk())
        assert p.policy_id.startswith("emp-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_missing_connection(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(connection_id=""))
        assert exc.value.code == "MISSING_CONNECTION"

    def test_register_invalid_marking_level(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(marking_level="top-secret"))
        assert exc.value.code == "INVALID_MARKING_LEVEL"

    def test_register_invalid_export_action(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.register(self._mk(export_action="encrypt"))
        assert exc.value.code == "INVALID_EXPORT_ACTION"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionSecurityError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_filter_connection_id(self) -> None:
        self.eng.register(self._mk(name="a", connection_id="conn-1"))
        self.eng.register(self._mk(name="b", connection_id="conn-2"))
        assert len(self.eng.list(connection_id="conn-1")) == 1

    def test_update(self) -> None:
        p = self.eng.register(self._mk())
        updated = self.eng.update(p.policy_id, {"name": "new-name", "export_action": "mask"})
        assert updated.name == "new-name"
        assert updated.export_action == "mask"

    def test_delete(self) -> None:
        p = self.eng.register(self._mk())
        assert self.eng.delete(p.policy_id) is True
        assert self.eng.delete(p.policy_id) is False

    def test_evaluate_allow(self) -> None:
        p = self.eng.register(self._mk(export_action="allow"))
        result = self.eng.evaluate("conn-1", "col_a", ["restricted"], "hello")
        assert result.decision == "allowed"
        assert result.policy_id == p.policy_id

    def test_evaluate_deny(self) -> None:
        self.eng.register(self._mk(export_action="deny"))
        result = self.eng.evaluate("conn-1", "col_a", ["restricted"], "hello")
        assert result.decision == "denied"

    def test_evaluate_mask(self) -> None:
        self.eng.register(self._mk(export_action="mask", mask_character="*"))
        result = self.eng.evaluate("conn-1", "col_a", ["restricted"], "secret")
        assert result.decision == "masked"
        assert result.masked_value == "******"

    def test_evaluate_redact(self) -> None:
        self.eng.register(self._mk(export_action="redact", redact_text="[REDACTED]"))
        result = self.eng.evaluate("conn-1", "col_a", ["restricted"], "secret")
        assert result.decision == "redacted"
        assert result.masked_value == "[REDACTED]"

    def test_evaluate_no_match_default_allow(self) -> None:
        self.eng.register(self._mk(connection_id="other-conn"))
        result = self.eng.evaluate("conn-1", "col_a", ["public"], "data")
        assert result.decision == "allowed"
        assert result.policy_id is None

    def test_evaluate_column_specific(self) -> None:
        self.eng.register(self._mk(export_action="deny", affected_columns=["secret_col"]))
        r1 = self.eng.evaluate("conn-1", "secret_col", ["restricted"], "val")
        assert r1.decision == "denied"
        r2 = self.eng.evaluate("conn-1", "public_col", ["restricted"], "val")
        assert r2.decision == "allowed"

    def test_evaluate_priority_order(self) -> None:
        self.eng.register(self._mk(name="allow-high", export_action="allow", priority=10))
        self.eng.register(self._mk(name="deny-low", export_action="deny", priority=100))
        result = self.eng.evaluate("conn-1", "col", ["restricted"], "val")
        assert result.decision == "allowed"

    def test_evaluate_row(self) -> None:
        self.eng.register(self._mk(export_action="deny", affected_columns=["ssn"]))
        results = self.eng.evaluate_row("conn-1", [
            {"name": "name", "markings": ["public"], "value": "Alice"},
            {"name": "ssn", "markings": ["restricted"], "value": "123-45"},
        ])
        assert len(results) == 2
        assert results[0].decision == "allowed"
        assert results[1].decision == "denied"

    def test_can_export(self) -> None:
        assert self.eng.can_export("conn-1", ["public"]) is True
        self.eng.register(self._mk(export_action="deny"))
        assert self.eng.can_export("conn-1", ["restricted"]) is False

    def test_add_remove_affected_column(self) -> None:
        p = self.eng.register(self._mk(affected_columns=["col1"]))
        updated = self.eng.add_affected_column(p.policy_id, "col2")
        assert "col2" in updated.affected_columns
        updated2 = self.eng.remove_affected_column(p.policy_id, "col1")
        assert "col1" not in updated2.affected_columns

    def test_add_remove_affected_marking(self) -> None:
        self.eng.register(self._mk(affected_markings=["PII"]))
        p = self.eng.register(self._mk(affected_markings=["PII"]))
        updated = self.eng.add_affected_marking(p.policy_id, "FINANCIAL")
        assert "FINANCIAL" in updated.affected_markings
        updated2 = self.eng.remove_affected_marking(p.policy_id, "PII")
        assert "PII" not in updated2.affected_markings

    def test_list_evaluations(self) -> None:
        self.eng.register(self._mk())
        self.eng.evaluate("conn-1", "col", ["restricted"], "val")
        evals = self.eng.list_evaluations()
        assert len(evals) == 1

    def test_max_policies_eviction(self) -> None:
        from aos_api.data_connection_security import _MAX_EXPORTABLE_MARKING_POLICIES
        for i in range(_MAX_EXPORTABLE_MARKING_POLICIES + 5):
            self.eng.register(ExportableMarkingPolicy(name=f"p-{i}", connection_id=f"c-{i}"))
        assert len(self.eng._policies) == _MAX_EXPORTABLE_MARKING_POLICIES


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_execution_policy_singleton(self) -> None:
        a = get_webhook_execution_policy_engine()
        b = get_webhook_execution_policy_engine()
        assert a is b

    def test_egress_policy_singleton(self) -> None:
        a = get_egress_policy_engine()
        b = get_egress_policy_engine()
        assert a is b

    def test_exportable_marking_singleton(self) -> None:
        a = get_exportable_marking_engine()
        b = get_exportable_marking_engine()
        assert a is b
