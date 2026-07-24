"""W2-Z · Pipeline 类型语义组测试：#94/#95/#96.

覆盖 PipelineTypeEngine / IncrementalPipelineEngine / StreamingPipelineEngine。
"""
from __future__ import annotations

import pytest

from aos_api.pipeline_type_semantics import (
    ChangeRecord,
    PipelineTypeError,
    PipelineTypeEngine,
    PipelineTypeSpec,
    StreamEvent,
    StreamingPipelineEngine,
    IncrementalPipelineEngine,
    WindowSpec,
    get_incremental_engine,
    get_pipeline_type_engine,
    get_streaming_engine,
)


# ════════════════════ #94 PipelineTypeEngine ════════════════════

class TestPipelineType:
    def setup_method(self) -> None:
        self.eng = PipelineTypeEngine()

    def test_list_default_three_types(self):
        items = self.eng.list()
        types = {s.type for s in items}
        assert types == {"batch", "incremental", "streaming"}

    def test_get_batch(self):
        s = self.eng.get("batch")
        assert s.type == "batch"
        assert s.trigger_semantics == "scheduled"
        assert s.default_write_mode == "append"

    def test_get_not_found(self):
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.get("nonexistent")
        assert ei.value.code == "NOT_FOUND"

    def test_register_custom(self):
        spec = PipelineTypeSpec(
            type="batch", name="自定义批处理",
            trigger_semantics="scheduled", fault_strategy="restart",
            state_machine=["pending", "running"],
        )
        out = self.eng.register(spec)
        assert out.type == "batch"
        assert out.name == "自定义批处理"

    def test_register_invalid_type(self):
        spec = PipelineTypeSpec(
            type="unknown", name="x",
            trigger_semantics="scheduled", fault_strategy="restart",
        )
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.register(spec)
        assert ei.value.code == "INVALID_TYPE"

    def test_register_invalid_trigger(self):
        spec = PipelineTypeSpec(
            type="batch", name="x",
            trigger_semantics="unknown", fault_strategy="restart",
        )
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.register(spec)
        assert ei.value.code == "INVALID_TRIGGER"

    def test_register_invalid_fault(self):
        spec = PipelineTypeSpec(
            type="batch", name="x",
            trigger_semantics="scheduled", fault_strategy="unknown",
        )
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.register(spec)
        assert ei.value.code == "INVALID_FAULT_STRATEGY"

    def test_update(self):
        out = self.eng.update("batch", {"description": "更新描述", "enabled": False})
        assert out.description == "更新描述"
        assert out.enabled is False
        assert self.eng.get("batch").enabled is False

    def test_update_immutable_type(self):
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.update("batch", {"type": "streaming"})
        assert ei.value.code == "IMMUTABLE_FIELD"

    def test_delete(self):
        self.eng.delete("batch")
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.get("batch")
        assert ei.value.code == "NOT_FOUND"

    def test_list_enabled_only(self):
        self.eng.update("batch", {"enabled": False})
        items = self.eng.list(enabled_only=True)
        types = {s.type for s in items}
        assert "batch" not in types
        assert "incremental" in types

    def test_validate_run_match(self):
        r = self.eng.validate_run("batch", "append")
        assert r["ok"] is True
        assert r["hint"] == ""

    def test_validate_run_mismatch(self):
        r = self.eng.validate_run("batch", "upsert")
        assert r["ok"] is False
        assert "不匹配" in r["hint"]

    def test_get_custom_not_found(self):
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.get("custom-xyz")
        assert ei.value.code == "NOT_FOUND"


# ════════════════════ #95 IncrementalPipelineEngine ════════════════════

class TestIncremental:
    def setup_method(self) -> None:
        self.eng = IncrementalPipelineEngine()

    def test_set_watermark(self):
        wm = self.eng.set_watermark("p1", "updated_at", "2026-01-01T00:00:00Z")
        assert wm.pipeline_id == "p1"
        assert wm.value == "2026-01-01T00:00:00Z"
        assert wm.field == "updated_at"

    def test_get_watermark_unset(self):
        wm = self.eng.get_watermark("p-noexist")
        assert wm.value == ""
        assert wm.pipeline_id == "p-noexist"

    def test_register_change_insert(self):
        rec = ChangeRecord(
            pipeline_id="p1", operation="insert", pk="k1",
            watermark_value="2026-01-01",
        )
        out = self.eng.register_change(rec)
        assert out.id != ""
        assert out.operation == "insert"

    def test_register_change_update(self):
        rec = ChangeRecord(pipeline_id="p1", operation="update", pk="k1")
        out = self.eng.register_change(rec)
        assert out.operation == "update"

    def test_register_change_delete(self):
        rec = ChangeRecord(pipeline_id="p1", operation="delete", pk="k1")
        out = self.eng.register_change(rec)
        assert out.operation == "delete"

    def test_register_change_invalid_op(self):
        rec = ChangeRecord(pipeline_id="p1", operation="unknown", pk="k1")
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.register_change(rec)
        assert ei.value.code == "INVALID_OPERATION"

    def test_list_changes_default(self):
        for i in range(3):
            self.eng.register_change(ChangeRecord(
                pipeline_id="p1", operation="insert", pk=f"k{i}",
            ))
        items = self.eng.list_changes("p1")
        assert len(items) == 3

    def test_list_changes_by_op(self):
        self.eng.register_change(ChangeRecord(
            pipeline_id="p1", operation="insert", pk="k1",
        ))
        self.eng.register_change(ChangeRecord(
            pipeline_id="p1", operation="update", pk="k2",
        ))
        items = self.eng.list_changes("p1", op="update")
        assert len(items) == 1
        assert items[0].operation == "update"

    def test_list_changes_since_watermark(self):
        self.eng.register_change(ChangeRecord(
            pipeline_id="p1", operation="insert", pk="k1",
            watermark_value="2026-01-01",
        ))
        self.eng.register_change(ChangeRecord(
            pipeline_id="p1", operation="insert", pk="k2",
            watermark_value="2026-01-02",
        ))
        items = self.eng.list_changes("p1", since_watermark="2026-01-01")
        assert len(items) == 1
        assert items[0].watermark_value == "2026-01-02"

    def test_create_checkpoint(self):
        ckpt = self.eng.create_checkpoint("p1")
        assert ckpt.status == "pending"
        assert ckpt.sequence == 1

    def test_commit_checkpoint(self):
        ckpt = self.eng.create_checkpoint("p1")
        out = self.eng.commit_checkpoint(ckpt.id)
        assert out.status == "committed"
        assert out.committed_at > 0

    def test_commit_checkpoint_not_found(self):
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.commit_checkpoint("nonexistent")
        assert ei.value.code == "NOT_FOUND"

    def test_list_checkpoints(self):
        self.eng.create_checkpoint("p1")
        self.eng.create_checkpoint("p1")
        items = self.eng.list_checkpoints("p1")
        assert len(items) == 2
        assert items[1].sequence == 2

    def test_process_increment_with_changes(self):
        self.eng.set_watermark("p1", "updated_at", "2026-01-01")
        self.eng.register_change(ChangeRecord(
            pipeline_id="p1", operation="insert", pk="k1",
            watermark_value="2026-01-02",
        ))
        result = self.eng.process_increment("p1")
        assert result.status == "completed"
        assert result.rows_processed == 1
        assert result.new_watermark == "2026-01-02"
        assert result.checkpoint_id != ""

    def test_process_increment_no_changes(self):
        result = self.eng.process_increment("p1")
        assert result.status == "skipped"
        assert result.rows_processed == 0

    def test_process_increment_creates_and_commits_checkpoint(self):
        changes = [
            ChangeRecord(
                pipeline_id="p1", operation="insert", pk="k1",
                watermark_value="2026-01-03",
            )
        ]
        result = self.eng.process_increment("p1", changes=changes)
        assert result.checkpoint_id != ""
        ckpts = self.eng.list_checkpoints("p1")
        assert ckpts[-1].status == "committed"


# ════════════════════ #96 StreamingPipelineEngine ════════════════════

class TestStreaming:
    def setup_method(self) -> None:
        self.eng = StreamingPipelineEngine()

    def test_register_window_tumbling(self):
        spec = WindowSpec(type="tumbling", size_ms=1000)
        out = self.eng.register_window("p1", spec)
        assert out.type == "tumbling"
        assert out.size_ms == 1000

    def test_register_window_sliding(self):
        spec = WindowSpec(type="sliding", size_ms=1000, slide_ms=500)
        out = self.eng.register_window("p1", spec)
        assert out.slide_ms == 500

    def test_register_window_session(self):
        spec = WindowSpec(type="session", gap_ms=2000)
        out = self.eng.register_window("p1", spec)
        assert out.gap_ms == 2000

    def test_register_window_invalid_type(self):
        spec = WindowSpec(type="unknown")
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.register_window("p1", spec)
        assert ei.value.code == "INVALID_WINDOW_TYPE"

    def test_get_window(self):
        spec = WindowSpec(type="tumbling", size_ms=1000)
        self.eng.register_window("p1", spec)
        out = self.eng.get_window("p1")
        assert out.type == "tumbling"

    def test_ingest_tumbling_assigns_window(self):
        self.eng.register_window("p1", WindowSpec(type="tumbling", size_ms=1000))
        evt = StreamEvent(pipeline_id="p1", key="k1", event_ts=1500)
        out = self.eng.ingest(evt)
        assert out.processed is True
        wins = self.eng.list_windows("p1")
        assert len(wins) == 1
        assert wins[0].start_ts == 1000
        assert wins[0].end_ts == 2000

    def test_ingest_sliding_multiple_windows(self):
        self.eng.register_window(
            "p1", WindowSpec(type="sliding", size_ms=1000, slide_ms=500),
        )
        # ts=1200，覆盖窗口 [1000,2000) 和 [500,1500)
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=1200))
        wins = self.eng.list_windows("p1")
        assert len(wins) == 2

    def test_ingest_session_merge(self):
        self.eng.register_window(
            "p1", WindowSpec(type="session", gap_ms=2000),
        )
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=1000))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=2500))
        # 间隔 1500 <= gap 2000，合并到同一会话
        wins = self.eng.list_windows("p1")
        assert len(wins) == 1
        assert wins[0].end_ts == 2500

    def test_ingest_session_new_when_gap_exceeded(self):
        self.eng.register_window(
            "p1", WindowSpec(type="session", gap_ms=1000),
        )
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=1000))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=5000))
        # 间隔 4000 > gap 1000，新建会话
        wins = self.eng.list_windows("p1")
        assert len(wins) == 2

    def test_list_events(self):
        self.eng.register_window("p1", WindowSpec(type="tumbling", size_ms=1000))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=100))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k2", event_ts=200))
        items = self.eng.list_events("p1")
        assert len(items) == 2

    def test_list_events_processed_only(self):
        self.eng.register_window("p1", WindowSpec(type="tumbling", size_ms=1000))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=100))
        items = self.eng.list_events("p1", processed_only=True)
        assert len(items) == 1
        assert items[0].processed is True

    def test_list_windows_open_only(self):
        self.eng.register_window("p1", WindowSpec(type="tumbling", size_ms=1000))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=100))
        wins = self.eng.list_windows("p1", open_only=True)
        assert len(wins) == 1
        assert wins[0].open is True

    def test_advance_watermark_closes_windows(self):
        self.eng.register_window("p1", WindowSpec(type="tumbling", size_ms=1000))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=500))
        # 窗口 [0,1000)，watermark=1000 关闭它
        result = self.eng.advance_watermark("p1", 1000)
        assert result.windows_closed == 1
        wins = self.eng.list_windows("p1", open_only=True)
        assert len(wins) == 0

    def test_advance_watermark_returns_result(self):
        self.eng.register_window("p1", WindowSpec(type="tumbling", size_ms=1000))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=500))
        result = self.eng.advance_watermark("p1", 2000)
        assert result.watermark_advanced == 2000
        assert result.processed == 1

    def test_close_window_manual(self):
        self.eng.register_window("p1", WindowSpec(type="tumbling", size_ms=1000))
        self.eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=500))
        wins = self.eng.list_windows("p1")
        wid = wins[0].window_id
        out = self.eng.close_window(wid)
        assert out.open is False
        assert out.emitted is True

    def test_close_window_not_found(self):
        with pytest.raises(PipelineTypeError) as ei:
            self.eng.close_window("nonexistent")
        assert ei.value.code == "NOT_FOUND"


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_get_pipeline_type_engine_singleton(self):
        a = get_pipeline_type_engine()
        b = get_pipeline_type_engine()
        assert a is b

    def test_get_incremental_engine_singleton(self):
        a = get_incremental_engine()
        b = get_incremental_engine()
        assert a is b

    def test_get_streaming_engine_singleton(self):
        a = get_streaming_engine()
        b = get_streaming_engine()
        assert a is b


# ════════════════════ 扩展用例 ════════════════════

class TestExtended:
    def test_register_window_tumbling_invalid_size(self):
        eng = StreamingPipelineEngine()
        with pytest.raises(PipelineTypeError) as ei:
            eng.register_window("p1", WindowSpec(type="tumbling", size_ms=0))
        assert ei.value.code == "INVALID_SIZE"

    def test_register_window_sliding_invalid_size(self):
        eng = StreamingPipelineEngine()
        with pytest.raises(PipelineTypeError) as ei:
            eng.register_window(
                "p1", WindowSpec(type="sliding", size_ms=0, slide_ms=500),
            )
        assert ei.value.code == "INVALID_SIZE"

    def test_register_window_session_invalid_gap(self):
        eng = StreamingPipelineEngine()
        with pytest.raises(PipelineTypeError) as ei:
            eng.register_window("p1", WindowSpec(type="session", gap_ms=0))
        assert ei.value.code == "INVALID_GAP"

    def test_ingest_without_window_spec(self):
        eng = StreamingPipelineEngine()
        with pytest.raises(PipelineTypeError) as ei:
            eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=100))
        assert ei.value.code == "NOT_FOUND"

    def test_advance_watermark_regress(self):
        eng = StreamingPipelineEngine()
        eng.advance_watermark("p1", 1000)
        with pytest.raises(PipelineTypeError) as ei:
            eng.advance_watermark("p1", 500)
        assert ei.value.code == "WATERMARK_REGRESS"

    def test_commit_checkpoint_already_committed(self):
        eng = IncrementalPipelineEngine()
        ckpt = eng.create_checkpoint("p1")
        eng.commit_checkpoint(ckpt.id)
        with pytest.raises(PipelineTypeError) as ei:
            eng.commit_checkpoint(ckpt.id)
        assert ei.value.code == "ALREADY_COMMITTED"

    def test_register_change_invalid_pk(self):
        eng = IncrementalPipelineEngine()
        with pytest.raises(PipelineTypeError) as ei:
            eng.register_change(ChangeRecord(pipeline_id="p1", operation="insert", pk=""))
        assert ei.value.code == "INVALID_PK"

    def test_set_watermark_empty_field(self):
        eng = IncrementalPipelineEngine()
        with pytest.raises(PipelineTypeError) as ei:
            eng.set_watermark("p1", "", "v1")
        assert ei.value.code == "INVALID_FIELD"

    def test_update_not_found(self):
        eng = PipelineTypeEngine()
        with pytest.raises(PipelineTypeError) as ei:
            eng.update("nonexistent", {"name": "x"})
        assert ei.value.code == "NOT_FOUND"

    def test_delete_not_found(self):
        eng = PipelineTypeEngine()
        with pytest.raises(PipelineTypeError) as ei:
            eng.delete("nonexistent")
        assert ei.value.code == "NOT_FOUND"

    def test_max_changes_eviction(self):
        eng = IncrementalPipelineEngine()
        for i in range(205):
            eng.register_change(ChangeRecord(
                pipeline_id="p1", operation="insert", pk=f"k{i}",
            ))
        items = eng.list_changes("p1", limit=300)
        assert len(items) == 200

    def test_tumbling_floor_alignment(self):
        """验证 tumbling 窗口 floor 对齐。"""
        eng = StreamingPipelineEngine()
        eng.register_window("p1", WindowSpec(type="tumbling", size_ms=1000))
        eng.ingest(StreamEvent(pipeline_id="p1", key="k1", event_ts=999))
        eng.ingest(StreamEvent(pipeline_id="p1", key="k2", event_ts=1001))
        wins = eng.list_windows("p1")
        # 999 → [0,1000), 1001 → [1000,2000)
        starts = sorted({w.start_ts for w in wins})
        assert starts == [0, 1000]
