"""W2-Y · 契约与安全标记组单测：#88 CAP 约束 + #99 安全标记传播 + #100 标记移除策略."""
from __future__ import annotations

import pytest

from aos_api.cap_and_markings import (
    CapAndMarkingsError,
    CapConstraintEngine,
    MarkingPropagationConfig,
    MarkingPropagationEngine,
    MarkingRecord,
    MarkingRemovalEngine,
    MarkingRemovalPolicy,
)


# ════════════════════════════════════════════════════════════════
# #88 CapConstraintEngine（15）
# ════════════════════════════════════════════════════════════════

class TestCapConstraint:
    """#88 · CAP 约束。"""

    def test_list_rules_default(self):
        eng = CapConstraintEngine()
        items = eng.list_rules()
        assert len(items) == 7
        codes = [r.code for r in items]
        assert codes == ["CAP-01", "CAP-02", "CAP-03", "CAP-04", "CAP-05", "CAP-06", "CAP-07"]

    def test_get_rule_cap_01(self):
        eng = CapConstraintEngine()
        r = eng.get_rule("CAP-01")
        assert r.code == "CAP-01"
        assert "FUNC-03" in r.title or "Capability" in r.title

    def test_get_rule_not_found(self):
        eng = CapConstraintEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.get_rule("CAP-99")
        assert exc.value.code == "NOT_FOUND"

    def test_update_rule(self):
        eng = CapConstraintEngine()
        eng.update_rule("CAP-01", {"enabled": False, "enforcement": "audit"})
        r = eng.get_rule("CAP-01")
        assert r.enabled is False
        assert r.enforcement == "audit"

    def test_list_rules_enabled_only(self):
        eng = CapConstraintEngine()
        eng.update_rule("CAP-01", {"enabled": False})
        items = eng.list_rules(enabled_only=True)
        assert all(r.enabled for r in items)
        assert len(items) == 6

    def test_check_cap_01_block(self):
        eng = CapConstraintEngine()
        # CAP-01 默认 enforcement=block
        v = eng.check("CAP-01", actor="alice", target_type="function", target_id="fn-1")
        assert v.resolution == "blocked"
        assert v.code == "CAP-01"
        assert v.actor == "alice"

    def test_check_cap_02_audit(self):
        eng = CapConstraintEngine()
        # CAP-02 默认 enforcement=audit
        v = eng.check("CAP-02", actor="alice", target_type="logic_run", target_id="lr-1")
        assert v.resolution == "audited"

    def test_check_disabled_rule_dry_run(self):
        eng = CapConstraintEngine()
        eng.update_rule("CAP-01", {"enabled": False})
        v = eng.check("CAP-01", actor="alice", target_type="function", target_id="fn-1")
        assert v.resolution == "dry_run_passed"

    def test_check_dry_run_enforcement(self):
        eng = CapConstraintEngine()
        eng.update_rule("CAP-01", {"enforcement": "dry_run"})
        v = eng.check("CAP-01", actor="alice", target_type="function", target_id="fn-1")
        assert v.resolution == "dry_run_passed"

    def test_list_violations_default(self):
        eng = CapConstraintEngine()
        eng.check("CAP-01", actor="alice", target_type="function", target_id="fn-1")
        eng.check("CAP-02", actor="bob", target_type="logic_run", target_id="lr-1")
        items = eng.list_violations()
        assert len(items) == 2

    def test_list_violations_by_code(self):
        eng = CapConstraintEngine()
        eng.check("CAP-01", actor="alice", target_type="function", target_id="fn-1")
        eng.check("CAP-02", actor="bob", target_type="logic_run", target_id="lr-1")
        items = eng.list_violations(code="CAP-01")
        assert len(items) == 1
        assert items[0].code == "CAP-01"

    def test_list_violations_by_target_type(self):
        eng = CapConstraintEngine()
        eng.check("CAP-01", actor="alice", target_type="function", target_id="fn-1")
        eng.check("CAP-02", actor="bob", target_type="logic_run", target_id="lr-1")
        items = eng.list_violations(target_type="function")
        assert len(items) == 1
        assert items[0].target_type == "function"

    def test_get_violation_single(self):
        eng = CapConstraintEngine()
        v = eng.check("CAP-01", actor="alice", target_type="function", target_id="fn-1")
        got = eng.get_violation(v.id)
        assert got.id == v.id
        assert got.actor == "alice"

    def test_get_violation_not_found(self):
        eng = CapConstraintEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.get_violation("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_max_200_violations_eviction(self):
        eng = CapConstraintEngine()
        first_id = None
        for i in range(210):
            v = eng.check("CAP-01", actor="alice", target_type="function", target_id=f"fn-{i}")
            if i == 0:
                first_id = v.id
        with pytest.raises(CapAndMarkingsError):
            eng.get_violation(first_id)
        # 仍有 200 条
        items = eng.list_violations(limit=500)
        assert len(items) == 200


# ════════════════════════════════════════════════════════════════
# #99 MarkingPropagationEngine（15）
# ════════════════════════════════════════════════════════════════

class TestMarkingPropagation:
    """#99 · 安全标记传播。"""

    def test_set_config(self):
        eng = MarkingPropagationEngine()
        cfg = MarkingPropagationConfig(
            project_id="p1", object_type="Order",
            stop_propagating=True,
        )
        out = eng.set_config(cfg)
        assert out.project_id == "p1"
        assert out.stop_propagating is True

    def test_get_config(self):
        eng = MarkingPropagationEngine()
        eng.set_config(MarkingPropagationConfig(
            project_id="p1", object_type="Order", stop_propagating=True,
        ))
        cfg = eng.get_config("p1", "Order")
        assert cfg.stop_propagating is True

    def test_get_config_default_fallback(self):
        eng = MarkingPropagationEngine()
        cfg = eng.get_config("p1", "Order")
        # 未设置时返回默认
        assert cfg.stop_propagating is False
        assert cfg.inherit_from_parent is True

    def test_list_configs(self):
        eng = MarkingPropagationEngine()
        eng.set_config(MarkingPropagationConfig(project_id="p1", object_type="Order"))
        eng.set_config(MarkingPropagationConfig(project_id="p1", object_type="Customer"))
        eng.set_config(MarkingPropagationConfig(project_id="p2", object_type="Order"))
        items = eng.list_configs()
        assert len(items) == 3

    def test_list_configs_by_project(self):
        eng = MarkingPropagationEngine()
        eng.set_config(MarkingPropagationConfig(project_id="p1", object_type="Order"))
        eng.set_config(MarkingPropagationConfig(project_id="p2", object_type="Order"))
        items = eng.list_configs(project_id="p1")
        assert len(items) == 1
        assert items[0].project_id == "p1"

    def test_record_marking(self):
        eng = MarkingPropagationEngine()
        m = eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Order", object_id="o1",
            security_label="sensitive",
        ))
        assert m.id.startswith("mark-")
        assert m.security_label == "sensitive"

    def test_get_marking(self):
        eng = MarkingPropagationEngine()
        m = eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Order", object_id="o1",
            security_label="sensitive",
        ))
        got = eng.get_marking("p1", "Order", "o1")
        assert got.id == m.id

    def test_get_marking_not_found(self):
        eng = MarkingPropagationEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.get_marking("p1", "Order", "nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_markings_default(self):
        eng = MarkingPropagationEngine()
        eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Order", object_id="o1", security_label="sensitive",
        ))
        eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Customer", object_id="c1", security_label="public",
        ))
        items = eng.list_markings(project_id="p1")
        assert len(items) == 2

    def test_list_markings_by_security_label(self):
        eng = MarkingPropagationEngine()
        eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Order", object_id="o1", security_label="sensitive",
        ))
        eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Customer", object_id="c1", security_label="public",
        ))
        items = eng.list_markings(project_id="p1", security_label="sensitive")
        assert len(items) == 1
        assert items[0].security_label == "sensitive"

    def test_propagate_normal(self):
        eng = MarkingPropagationEngine()
        # source 标记
        eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Order", object_id="o1",
            security_label="sensitive",
        ))
        # 默认配置：stop_propagating=False
        downstream = eng.propagate(
            project_id="p1",
            source_object_type="Order", source_object_id="o1",
            downstream_object_type="OrderItem", downstream_object_id="i1",
        )
        assert downstream.security_label == "sensitive"
        assert downstream.is_inherited is True
        assert downstream.propagated_from == "o1"

    def test_propagate_stop_propagating(self):
        eng = MarkingPropagationEngine()
        eng.set_config(MarkingPropagationConfig(
            project_id="p1", object_type="Order", stop_propagating=True,
        ))
        eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Order", object_id="o1",
            security_label="sensitive",
        ))
        downstream = eng.propagate(
            project_id="p1",
            source_object_type="Order", source_object_id="o1",
            downstream_object_type="OrderItem", downstream_object_id="i1",
        )
        # stop_propagating=True → 不继承
        assert downstream.is_inherited is False
        assert downstream.security_label == "public"
        assert downstream.propagated_from == ""

    def test_propagate_default_config_inherits(self):
        eng = MarkingPropagationEngine()
        eng.record_marking(MarkingRecord(
            project_id="p1", object_type="Order", object_id="o1",
            security_label="restricted",
        ))
        # 未设置配置 → 默认 stop_propagating=False → 继承
        downstream = eng.propagate(
            project_id="p1",
            source_object_type="Order", source_object_id="o1",
            downstream_object_type="OrderItem", downstream_object_id="i1",
        )
        assert downstream.security_label == "restricted"
        assert downstream.is_inherited is True

    def test_propagate_source_not_found(self):
        eng = MarkingPropagationEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.propagate(
                project_id="p1",
                source_object_type="Order", source_object_id="nonexistent",
                downstream_object_type="OrderItem", downstream_object_id="i1",
            )
        assert exc.value.code == "NOT_FOUND"

    def test_max_200_markings_eviction(self):
        eng = MarkingPropagationEngine()
        first_key = None
        for i in range(210):
            m = eng.record_marking(MarkingRecord(
                project_id="p1", object_type="Order", object_id=f"o{i}",
                security_label="sensitive",
            ))
            if i == 0:
                first_key = ("p1", "Order", "o0")
        # 第一条已被淘汰
        with pytest.raises(CapAndMarkingsError):
            eng.get_marking(*first_key)
        # 仍有 200 条
        items = eng.list_markings(project_id="p1", limit=500)
        assert len(items) == 200


# ════════════════════════════════════════════════════════════════
# #100 MarkingRemovalEngine（15）
# ════════════════════════════════════════════════════════════════

class TestMarkingRemoval:
    """#100 · 标记移除策略。"""

    def test_register_policy(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive", "restricted"],
        ))
        assert p.id.startswith("rm-pol-")
        assert p.strategy == "filter_out"

    def test_get_policy(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"],
        ))
        got = eng.get_policy(p.id)
        assert got.id == p.id

    def test_get_policy_not_found(self):
        eng = MarkingRemovalEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.get_policy("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_policies_default(self):
        eng = MarkingRemovalEngine()
        eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"],
        ))
        eng.register_policy(MarkingRemovalPolicy(
            project_id="p2", output_object_type="Customer",
            strategy="filter_in", keep_labels=["public"],
        ))
        items = eng.list_policies()
        assert len(items) == 2

    def test_list_policies_by_project(self):
        eng = MarkingRemovalEngine()
        eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"],
        ))
        eng.register_policy(MarkingRemovalPolicy(
            project_id="p2", output_object_type="Customer",
            strategy="filter_in", keep_labels=["public"],
        ))
        items = eng.list_policies(project_id="p1")
        assert len(items) == 1
        assert items[0].project_id == "p1"

    def test_list_policies_enabled_only(self):
        eng = MarkingRemovalEngine()
        eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"], enabled=True,
        ))
        eng.register_policy(MarkingRemovalPolicy(
            project_id="p2", output_object_type="Customer",
            strategy="filter_in", keep_labels=["public"], enabled=False,
        ))
        items = eng.list_policies(enabled_only=True)
        assert len(items) == 1
        assert items[0].enabled is True

    def test_update_policy(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"],
        ))
        eng.update_policy(p.id, {"enabled": False, "removed_labels": ["sensitive", "restricted"]})
        got = eng.get_policy(p.id)
        assert got.enabled is False
        assert got.removed_labels == ["sensitive", "restricted"]

    def test_delete_policy(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"],
        ))
        assert eng.delete_policy(p.id) is True
        assert eng.delete_policy(p.id) is False

    def test_apply_filter_in(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_in", keep_labels=["public", "internal"],
        ))
        r = eng.apply(
            policy_id=p.id, object_id="o1",
            original_labels=["public", "internal", "sensitive", "restricted"],
        )
        assert r.final_labels == ["public", "internal"]
        assert set(r.removed_labels) == {"sensitive", "restricted"}

    def test_apply_filter_out(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive", "restricted"],
        ))
        r = eng.apply(
            policy_id=p.id, object_id="o1",
            original_labels=["public", "internal", "sensitive", "restricted"],
        )
        assert r.final_labels == ["public", "internal"]
        assert set(r.removed_labels) == {"sensitive", "restricted"}

    def test_apply_filter_in_skip_inherited(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_in", keep_labels=["public"],
            apply_to_inherited=False,
        ))
        # original 包含继承标记 sensitive
        r = eng.apply(
            policy_id=p.id, object_id="o1",
            original_labels=["public", "internal", "sensitive"],
            inherited_labels=["sensitive"],
        )
        # 非继承的 [public, internal] 经 filter_in 仅留 public
        # 继承的 sensitive 不处理，保留
        assert "public" in r.final_labels
        assert "sensitive" in r.final_labels
        assert "internal" not in r.final_labels
        assert r.skipped_inherited == 1

    def test_apply_disabled_policy(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"], enabled=False,
        ))
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.apply(policy_id=p.id, object_id="o1", original_labels=["public"])
        assert exc.value.code == "POLICY_DISABLED"

    def test_apply_unknown_policy(self):
        eng = MarkingRemovalEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.apply(policy_id="nonexistent", object_id="o1", original_labels=["public"])
        assert exc.value.code == "NOT_FOUND"

    def test_list_results(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"],
        ))
        eng.apply(policy_id=p.id, object_id="o1", original_labels=["public", "sensitive"])
        eng.apply(policy_id=p.id, object_id="o2", original_labels=["internal", "sensitive"])
        items = eng.list_results()
        assert len(items) == 2

    def test_max_200_results_eviction(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"],
        ))
        first_id = None
        for i in range(210):
            r = eng.apply(
                policy_id=p.id, object_id=f"o{i}",
                original_labels=["public", "sensitive"],
            )
            if i == 0:
                first_id = r.id
        # 第一条已被淘汰（不在 _results 中）
        items = eng.list_results(limit=500)
        assert len(items) == 200
        assert first_id not in [r.id for r in items]


# ════════════════════════════════════════════════════════════════
# 补充：单例 + 边界
# ════════════════════════════════════════════════════════════════

class TestSingletons:
    """单例 getter 测试。"""

    def test_get_cap_constraint_engine_singleton(self):
        from aos_api.cap_and_markings import get_cap_constraint_engine
        a = get_cap_constraint_engine()
        b = get_cap_constraint_engine()
        assert a is b

    def test_get_marking_propagation_engine_singleton(self):
        from aos_api.cap_and_markings import get_marking_propagation_engine
        a = get_marking_propagation_engine()
        b = get_marking_propagation_engine()
        assert a is b

    def test_get_marking_removal_engine_singleton(self):
        from aos_api.cap_and_markings import get_marking_removal_engine
        a = get_marking_removal_engine()
        b = get_marking_removal_engine()
        assert a is b


class TestExtended:
    """边界用例。"""

    def test_register_invalid_strategy(self):
        eng = MarkingRemovalEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.register_policy(MarkingRemovalPolicy(
                project_id="p1", output_object_type="Order",
                strategy="invalid", removed_labels=["sensitive"],
            ))
        assert exc.value.code == "INVALID_STRATEGY"

    def test_register_filter_in_without_keep_labels(self):
        eng = MarkingRemovalEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.register_policy(MarkingRemovalPolicy(
                project_id="p1", output_object_type="Order",
                strategy="filter_in",  # 未指定 keep_labels
            ))
        assert exc.value.code == "INVALID_POLICY"

    def test_register_filter_out_without_removed_labels(self):
        eng = MarkingRemovalEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.register_policy(MarkingRemovalPolicy(
                project_id="p1", output_object_type="Order",
                strategy="filter_out",  # 未指定 removed_labels
            ))
        assert exc.value.code == "INVALID_POLICY"

    def test_record_marking_invalid_security_label(self):
        eng = MarkingPropagationEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.record_marking(MarkingRecord(
                project_id="p1", object_type="Order", object_id="o1",
                security_label="invalid",
            ))
        assert exc.value.code == "INVALID_SECURITY_LABEL"

    def test_update_rule_invalid_enforcement(self):
        eng = CapConstraintEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.update_rule("CAP-01", {"enforcement": "invalid"})
        assert exc.value.code == "INVALID_ENFORCEMENT"

    def test_update_rule_invalid_severity(self):
        eng = CapConstraintEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.update_rule("CAP-01", {"severity": "critical"})
        assert exc.value.code == "INVALID_SEVERITY"

    def test_update_rule_immutable_code(self):
        eng = CapConstraintEngine()
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.update_rule("CAP-01", {"code": "CAP-99"})
        assert exc.value.code == "IMMUTABLE_FIELD"

    def test_update_policy_immutable_id(self):
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["sensitive"],
        ))
        with pytest.raises(CapAndMarkingsError) as exc:
            eng.update_policy(p.id, {"id": "other-id"})
        assert exc.value.code == "IMMUTABLE_FIELD"

    def test_apply_filter_out_no_match(self):
        """filter_out 但 original 不含 removed_labels → 全保留。"""
        eng = MarkingRemovalEngine()
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_out", removed_labels=["restricted"],
        ))
        r = eng.apply(
            policy_id=p.id, object_id="o1",
            original_labels=["public", "internal"],
        )
        assert r.final_labels == ["public", "internal"]
        assert r.removed_labels == []

    def test_apply_filter_in_empty_keep_labels_edge(self):
        """filter_in + 空 keep_labels 但 original 也空 → final=[]（合法）。"""
        eng = MarkingRemovalEngine()
        # 注册时强制 keep_labels 非空，故这里直接修改内部状态
        p = eng.register_policy(MarkingRemovalPolicy(
            project_id="p1", output_object_type="Order",
            strategy="filter_in", keep_labels=["public"],
        ))
        # 直接改 keep_labels 为空（绕过 register 校验用于边界测试）
        policy = eng._policies[p.id]
        policy.keep_labels = []
        r = eng.apply(
            policy_id=p.id, object_id="o1",
            original_labels=["sensitive"],
        )
        assert r.final_labels == []
        assert r.removed_labels == ["sensitive"]
