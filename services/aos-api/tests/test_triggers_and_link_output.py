"""W2-AA · 触发器与 Ontology 链接输出组测试（#97 / #98 / #91）.

覆盖 EventTriggerEngine / CompositeTriggerEngine / LinkTypeOutputEngine 三引擎。
"""
from __future__ import annotations

import time

import pytest

from aos_api.triggers_and_link_output import (
    CompositeTrigger,
    CompositeTriggerEngine,
    EventTrigger,
    EventTriggerEngine,
    LinkTypeDefinition,
    LinkTypeOutputEngine,
    TriggersAndLinkOutputError,
    get_composite_trigger_engine,
    get_event_trigger_engine,
    get_link_type_output_engine,
)


# ════════════════════ EventTriggerEngine ════════════════════

class TestEventTrigger:
    def setup_method(self) -> None:
        self.eng = EventTriggerEngine()

    def _mk(self, **kw: object) -> EventTrigger:
        defaults: dict[str, object] = {
            "name": "et1",
            "event_source": "dataset_updated",
            "target_pipeline_id": "pl-1",
        }
        defaults.update(kw)
        return EventTrigger(**defaults)

    def test_register_returns_with_id(self) -> None:
        t = self.eng.register(self._mk())
        assert t.id.startswith("et-")
        assert t.fire_count == 0

    def test_register_invalid_event_source(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.register(self._mk(event_source="unknown"))
        assert exc.value.code == "INVALID_EVENT_SOURCE"

    def test_get_not_found(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b", event_source="schedule"))
        assert len(self.eng.list()) == 2

    def test_list_filter_event_source(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b", event_source="schedule"))
        items = self.eng.list(event_source="schedule")
        assert len(items) == 1
        assert items[0].event_source == "schedule"

    def test_list_enabled_only(self) -> None:
        self.eng.register(self._mk(name="a", enabled=False))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list(enabled_only=True)) == 1

    def test_update(self) -> None:
        t = self.eng.register(self._mk())
        updated = self.eng.update(t.id, {"name": "renamed", "enabled": False})
        assert updated.name == "renamed"
        assert updated.enabled is False

    def test_delete(self) -> None:
        t = self.eng.register(self._mk())
        assert self.eng.delete(t.id) is True
        assert self.eng.delete(t.id) is False

    def test_fire_success(self) -> None:
        t = self.eng.register(self._mk())
        f = self.eng.fire(t.id, {"k": "v"})
        assert f.status == "fired"
        assert f.trigger_name == "et1"
        # fire_count 推进
        t2 = self.eng.get(t.id)
        assert t2.fire_count == 1
        assert t2.last_fired_at > 0

    def test_fire_disabled_skipped(self) -> None:
        t = self.eng.register(self._mk(enabled=False))
        f = self.eng.fire(t.id)
        assert f.status == "skipped"
        # fire_count 不推进
        assert self.eng.get(t.id).fire_count == 0

    def test_fire_cooldown(self) -> None:
        t = self.eng.register(self._mk(cooldown_seconds=10.0))
        # 第一次 fire 成功
        self.eng.fire(t.id)
        # 立即第二次应进入 cooldown
        f2 = self.eng.fire(t.id)
        assert f2.status == "cooldown"
        # fire_count 不再推进
        assert self.eng.get(t.id).fire_count == 1

    def test_list_fires(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.fire(t.id)
        self.eng.fire(t.id)
        fires = self.eng.list_fires()
        assert len(fires) == 2

    def test_list_fires_filter_trigger_id(self) -> None:
        t1 = self.eng.register(self._mk(name="t1"))
        t2 = self.eng.register(self._mk(name="t2"))
        self.eng.fire(t1.id)
        self.eng.fire(t2.id)
        items = self.eng.list_fires(trigger_id=t1.id)
        assert len(items) == 1
        assert items[0].trigger_id == t1.id

    def test_register_missing_name(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_fires_cap_eviction(self) -> None:
        # 200 条上限 FIFO 淘汰
        from aos_api.triggers_and_link_output import _MAX_FIRES
        t = self.eng.register(self._mk())
        for _ in range(_MAX_FIRES + 5):
            self.eng.fire(t.id)
        # 仅保留 _MAX_FIRES 条
        assert len(self.eng._fires) == _MAX_FIRES


# ════════════════════ CompositeTriggerEngine ════════════════════

class TestCompositeTrigger:
    def setup_method(self) -> None:
        self.eng = CompositeTriggerEngine()

    def _mk(self, **kw: object) -> CompositeTrigger:
        defaults: dict[str, object] = {
            "name": "ct1",
            "logic": "and",
            "child_trigger_ids": ["et-a", "et-b"],
            "target_pipeline_id": "pl-1",
        }
        defaults.update(kw)
        return CompositeTrigger(**defaults)

    def test_register_returns_with_id(self) -> None:
        t = self.eng.register(self._mk())
        assert t.id.startswith("ct-")

    def test_register_invalid_logic(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.register(self._mk(logic="xor"))
        assert exc.value.code == "INVALID_LOGIC"

    def test_register_empty_children(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.register(self._mk(child_trigger_ids=[]))
        assert exc.value.code == "EMPTY_CHILDREN"

    def test_get_not_found(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list()) == 2

    def test_list_enabled_only(self) -> None:
        self.eng.register(self._mk(name="a", enabled=False))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list(enabled_only=True)) == 1

    def test_update(self) -> None:
        t = self.eng.register(self._mk())
        updated = self.eng.update(t.id, {"logic": "or", "enabled": False})
        assert updated.logic == "or"
        assert updated.enabled is False

    def test_delete(self) -> None:
        t = self.eng.register(self._mk())
        assert self.eng.delete(t.id) is True
        assert self.eng.delete(t.id) is False

    def test_evaluate_and_all_true(self) -> None:
        t = self.eng.register(self._mk(logic="and"))
        result = self.eng.evaluate(t.id, {"et-a": True, "et-b": True})
        assert result["fired"] is True

    def test_evaluate_and_partial_false(self) -> None:
        t = self.eng.register(self._mk(logic="and"))
        result = self.eng.evaluate(t.id, {"et-a": True, "et-b": False})
        assert result["fired"] is False

    def test_evaluate_or_any_true(self) -> None:
        t = self.eng.register(self._mk(logic="or"))
        result = self.eng.evaluate(t.id, {"et-a": False, "et-b": True})
        assert result["fired"] is True

    def test_evaluate_or_all_false(self) -> None:
        t = self.eng.register(self._mk(logic="or"))
        result = self.eng.evaluate(t.id, {"et-a": False, "et-b": False})
        assert result["fired"] is False

    def test_evaluate_missing_child_defaults_false(self) -> None:
        # 缺失的子视为 False
        t = self.eng.register(self._mk(logic="and"))
        result = self.eng.evaluate(t.id, {"et-a": True})  # et-b 缺失
        assert result["fired"] is False
        assert result["detail"]["et-b"] is False

    def test_fire_pass(self) -> None:
        t = self.eng.register(self._mk(logic="or"))
        f = self.eng.fire(t.id, {"et-a": False, "et-b": True})
        assert f.status == "fired"
        assert self.eng.get(t.id).fire_count == 1

    def test_fire_skip(self) -> None:
        t = self.eng.register(self._mk(logic="and"))
        f = self.eng.fire(t.id, {"et-a": True, "et-b": False})
        assert f.status == "skipped"
        assert self.eng.get(t.id).fire_count == 0


# ════════════════════ LinkTypeOutputEngine ════════════════════

class TestLinkTypeOutput:
    def setup_method(self) -> None:
        self.eng = LinkTypeOutputEngine()

    def _mk(self, **kw: object) -> LinkTypeDefinition:
        defaults: dict[str, object] = {
            "name": "lt1",
            "cardinality": "many_to_one",
            "source_object_type": "Order",
            "target_object_type": "Customer",
            "source_pk_field": "id",
            "target_fk_field": "customer_id",
        }
        defaults.update(kw)
        return LinkTypeDefinition(**defaults)

    def test_register_returns_with_id(self) -> None:
        l = self.eng.register(self._mk())
        assert l.id.startswith("lt-")

    def test_register_invalid_cardinality(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.register(self._mk(cardinality="unknown"))
        assert exc.value.code == "INVALID_CARDINALITY"

    def test_register_missing_name(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_get_not_found(self) -> None:
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_get_by_name(self) -> None:
        l = self.eng.register(self._mk(name="find-me"))
        found = self.eng.get_by_name("find-me")
        assert found is not None
        assert found.id == l.id
        assert self.eng.get_by_name("missing") is None

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list()) == 2

    def test_list_filter_source_ot(self) -> None:
        self.eng.register(self._mk(name="a", source_object_type="Order"))
        self.eng.register(self._mk(name="b", source_object_type="Invoice"))
        items = self.eng.list(source_object_type="Order")
        assert len(items) == 1
        assert items[0].source_object_type == "Order"

    def test_list_filter_target_ot(self) -> None:
        self.eng.register(self._mk(name="a", target_object_type="Customer"))
        self.eng.register(self._mk(name="b", target_object_type="Supplier"))
        items = self.eng.list(target_object_type="Customer")
        assert len(items) == 1
        assert items[0].target_object_type == "Customer"

    def test_update(self) -> None:
        l = self.eng.register(self._mk())
        updated = self.eng.update(l.id, {"cardinality": "one_to_many", "display_name": "X"})
        assert updated.cardinality == "one_to_many"
        assert updated.display_name == "X"

    def test_delete(self) -> None:
        l = self.eng.register(self._mk())
        assert self.eng.delete(l.id) is True
        assert self.eng.delete(l.id) is False

    def test_infer_from_objects(self) -> None:
        rows = [{"id": 1, "customer_id": 100, "name": "order1"}]
        l = self.eng.infer_from_objects(
            source_ot="Order", target_ot="Customer",
            rows=rows, fk_field="customer_id", display_field="name",
        )
        assert l.cardinality == "many_to_one"
        assert l.name == "Order_to_Customer"
        assert l.source_pk_field == "id"
        assert l.target_fk_field == "customer_id"

    def test_preview_links(self) -> None:
        l = self.eng.register(self._mk(display_field="title"))
        rows = [
            {"id": 1, "customer_id": 100, "title": "o1"},
            {"id": 2, "customer_id": 101, "title": "o2"},
            {"id": 3, "customer_id": None, "title": "o3"},  # 缺 fk，跳过
        ]
        items = self.eng.preview_links(l.id, rows)
        assert len(items) == 2
        assert items[0]["source_object_id"] == "1"
        assert items[0]["target_object_id"] == "100"
        assert items[0]["display"] == "o1"
        assert items[0]["cardinality"] == "many_to_one"

    def test_register_name_duplicate(self) -> None:
        self.eng.register(self._mk(name="dup"))
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            self.eng.register(self._mk(name="dup"))
        assert exc.value.code == "NAME_DUPLICATE"


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_event_trigger_singleton(self) -> None:
        a = get_event_trigger_engine()
        b = get_event_trigger_engine()
        assert a is b

    def test_composite_trigger_singleton(self) -> None:
        a = get_composite_trigger_engine()
        b = get_composite_trigger_engine()
        assert a is b

    def test_link_type_output_singleton(self) -> None:
        a = get_link_type_output_engine()
        b = get_link_type_output_engine()
        assert a is b


# ════════════════════ 扩展：边界与回归 ════════════════════

class TestExtended:
    def test_event_trigger_update_invalid_source(self) -> None:
        eng = EventTriggerEngine()
        t = eng.register(EventTrigger(
            name="t", event_source="manual", target_pipeline_id="pl",
        ))
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.update(t.id, {"event_source": "bad"})
        assert exc.value.code == "INVALID_EVENT_SOURCE"

    def test_event_fire_records_payload(self) -> None:
        eng = EventTriggerEngine()
        t = eng.register(EventTrigger(
            name="t", event_source="manual", target_pipeline_id="pl",
        ))
        f = eng.fire(t.id, {"a": 1})
        assert f.event_payload == {"a": 1}

    def test_event_cooldown_zero_no_block(self) -> None:
        eng = EventTriggerEngine()
        t = eng.register(EventTrigger(
            name="t", event_source="manual", target_pipeline_id="pl",
            cooldown_seconds=0.0,
        ))
        f1 = eng.fire(t.id)
        f2 = eng.fire(t.id)
        assert f1.status == "fired"
        assert f2.status == "fired"  # cooldown=0 不拦截

    def test_composite_update_invalid_logic(self) -> None:
        eng = CompositeTriggerEngine()
        t = eng.register(CompositeTrigger(
            name="t", logic="and", child_trigger_ids=["a"], target_pipeline_id="pl",
        ))
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.update(t.id, {"logic": "bad"})
        assert exc.value.code == "INVALID_LOGIC"

    def test_composite_fire_records_logic_in_payload(self) -> None:
        eng = CompositeTriggerEngine()
        t = eng.register(CompositeTrigger(
            name="t", logic="or", child_trigger_ids=["a", "b"], target_pipeline_id="pl",
        ))
        f = eng.fire(t.id, {"a": True, "b": False})
        assert f.event_payload["logic"] == "or"
        assert f.event_payload["detail"]["a"] is True

    def test_link_update_invalid_cardinality(self) -> None:
        eng = LinkTypeOutputEngine()
        l = eng.register(LinkTypeDefinition(
            name="l", cardinality="one_to_many",
            source_object_type="A", target_object_type="B",
            source_pk_field="id", target_fk_field="a_id",
        ))
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.update(l.id, {"cardinality": "bad"})
        assert exc.value.code == "INVALID_CARDINALITY"

    def test_link_update_name_duplicate(self) -> None:
        eng = LinkTypeOutputEngine()
        eng.register(LinkTypeDefinition(
            name="l1", cardinality="one_to_many",
            source_object_type="A", target_object_type="B",
            source_pk_field="id", target_fk_field="a_id",
        ))
        l2 = eng.register(LinkTypeDefinition(
            name="l2", cardinality="one_to_many",
            source_object_type="A", target_object_type="B",
            source_pk_field="id", target_fk_field="a_id",
        ))
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.update(l2.id, {"name": "l1"})
        assert exc.value.code == "NAME_DUPLICATE"

    def test_link_infer_empty_rows(self) -> None:
        eng = LinkTypeOutputEngine()
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.infer_from_objects("A", "B", [], "fk")
        assert exc.value.code == "EMPTY_ROWS"

    def test_link_preview_respects_limit(self) -> None:
        eng = LinkTypeOutputEngine()
        l = eng.register(LinkTypeDefinition(
            name="l", cardinality="many_to_many",
            source_object_type="A", target_object_type="B",
            source_pk_field="id", target_fk_field="b_id",
        ))
        rows = [{"id": i, "b_id": i * 10} for i in range(10)]
        items = eng.preview_links(l.id, rows, limit=3)
        assert len(items) == 3

    def test_link_register_missing_object_type(self) -> None:
        eng = LinkTypeOutputEngine()
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.register(LinkTypeDefinition(
                name="l", cardinality="many_to_one",
                source_object_type="", target_object_type="B",
                source_pk_field="id", target_fk_field="b_id",
            ))
        assert exc.value.code == "MISSING_OBJECT_TYPE"

    def test_link_register_missing_key_field(self) -> None:
        eng = LinkTypeOutputEngine()
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.register(LinkTypeDefinition(
                name="l", cardinality="many_to_one",
                source_object_type="A", target_object_type="B",
                source_pk_field="", target_fk_field="b_id",
            ))
        assert exc.value.code == "MISSING_KEY_FIELD"

    def test_composite_register_missing_target(self) -> None:
        eng = CompositeTriggerEngine()
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.register(CompositeTrigger(
                name="t", logic="and", child_trigger_ids=["a"], target_pipeline_id="",
            ))
        assert exc.value.code == "MISSING_TARGET"

    def test_event_register_missing_target(self) -> None:
        eng = EventTriggerEngine()
        with pytest.raises(TriggersAndLinkOutputError) as exc:
            eng.register(EventTrigger(
                name="t", event_source="manual", target_pipeline_id="",
            ))
        assert exc.value.code == "MISSING_TARGET"
