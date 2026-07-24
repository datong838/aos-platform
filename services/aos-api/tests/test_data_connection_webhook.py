"""W2-AJ · Data Connection 流导出与 Webhook 组测试（#122 / #123 / #124）."""
from __future__ import annotations

import threading

import pytest

from aos_api.data_connection_webhook import (
    DataConnectionWebhookError,
    OutputFieldMapping,
    StreamExportEngine,
    StreamExportTask,
    WebhookOutputConfig,
    WebhookOutputEngine,
    WebhookPipeline,
    WebhookPipelineEngine,
    WebhookPipelineStep,
    get_stream_export_engine,
    get_webhook_output_engine,
    get_webhook_pipeline_engine,
)


# ════════════════════ StreamExportEngine ════════════════════

class TestStreamExport:
    def setup_method(self) -> None:
        self.eng = StreamExportEngine.__new__(StreamExportEngine)
        self.eng._tasks = {}
        self.eng._events = {}
        self.eng._partition_counters = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> StreamExportTask:
        defaults: dict[str, object] = {
            "name": "kafka-export",
            "source_stream": "stream-a",
            "target_type": "kafka",
            "partition_strategy": "round_robin",
            "batch_size": 100,
        }
        defaults.update(kw)
        return StreamExportTask(**defaults)

    def test_register_returns_with_id(self) -> None:
        t = self.eng.register(self._mk())
        assert t.id.startswith("sex-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_missing_source_stream(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(source_stream=""))
        assert exc.value.code == "MISSING_SOURCE_STREAM"

    def test_register_invalid_target_type(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(target_type="redis"))
        assert exc.value.code == "INVALID_TARGET_TYPE"

    def test_register_invalid_partition_strategy(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(partition_strategy="consistent_hash"))
        assert exc.value.code == "INVALID_PARTITION_STRATEGY"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_filter_status(self) -> None:
        t1 = self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        self.eng.start(t1.id)
        assert len(self.eng.list(status="running")) == 1

    def test_update(self) -> None:
        t = self.eng.register(self._mk())
        updated = self.eng.update(t.id, {"name": "new-name", "batch_size": 200})
        assert updated.name == "new-name"
        assert updated.batch_size == 200

    def test_delete(self) -> None:
        t = self.eng.register(self._mk())
        assert self.eng.delete(t.id) is True
        assert self.eng.delete(t.id) is False

    def test_start(self) -> None:
        t = self.eng.register(self._mk())
        started = self.eng.start(t.id)
        assert started.status == "running"

    def test_start_not_stopped(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.start(t.id)
        assert exc.value.code == "TASK_NOT_STOPPED"

    def test_stop(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        stopped = self.eng.stop(t.id)
        assert stopped.status == "stopped"

    def test_publish_event_success(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        ev = self.eng.publish_event(t.id, {"foo": "bar"}, "key1")
        assert ev.status == "sent"
        assert ev.key == "key1"
        assert ev.event_id.startswith("sev-")
        t2 = self.eng.get(t.id)
        assert t2.total_events == 1

    def test_publish_event_not_running(self) -> None:
        t = self.eng.register(self._mk())
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.publish_event(t.id, {"foo": "bar"})
        assert exc.value.code == "TASK_NOT_RUNNING"

    def test_publish_event_key_field_from_payload(self) -> None:
        t = self.eng.register(self._mk(key_field="user_id"))
        self.eng.start(t.id)
        ev = self.eng.publish_event(t.id, {"user_id": "u123", "data": "x"})
        assert ev.key == "u123"

    def test_publish_batch(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        events = [{"payload": {"a": 1}, "key": "k1"}, {"payload": {"b": 2}, "key": "k2"}]
        results = self.eng.publish_batch(t.id, events)
        assert len(results) == 2
        assert all(r.status == "sent" for r in results)

    def test_list_events_reverse_order(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        for i in range(5):
            self.eng.publish_event(t.id, {"i": i})
        evs = self.eng.list_events(t.id)
        assert len(evs) == 5
        assert evs[0].sent_at >= evs[-1].sent_at

    def test_max_tasks_eviction(self) -> None:
        from aos_api.data_connection_webhook import _MAX_STREAM_EXPORTS
        for i in range(_MAX_STREAM_EXPORTS + 5):
            self.eng.register(StreamExportTask(name=f"t-{i}", source_stream=f"s-{i}"))
        assert len(self.eng._tasks) == _MAX_STREAM_EXPORTS


# ════════════════════ WebhookPipelineEngine ════════════════════

class TestWebhookPipeline:
    def setup_method(self) -> None:
        self.eng = WebhookPipelineEngine.__new__(WebhookPipelineEngine)
        self.eng._pipelines = {}
        self.eng._runs = {}
        self.eng._all_runs = {}
        self.eng._lock = threading.Lock()

    def _step(self, **kw: object) -> WebhookPipelineStep:
        defaults: dict[str, object] = {
            "step_id": "step-1",
            "name": "call api",
            "url": "https://api.example.com/endpoint",
            "method": "POST",
            "auth_type": "none",
            "output_mapping": {"result": "data.value"},
        }
        defaults.update(kw)
        return WebhookPipelineStep(**defaults)

    def _mk(self, **kw: object) -> WebhookPipeline:
        defaults: dict[str, object] = {
            "name": "my-pipeline",
            "steps": [self._step(step_id="step-1"), self._step(step_id="step-2", name="step 2")],
            "status": "draft",
        }
        defaults.update(kw)
        return WebhookPipeline(**defaults)

    def test_register_returns_with_id(self) -> None:
        p = self.eng.register(self._mk())
        assert p.id.startswith("wpl-")
        assert len(p.steps) == 2

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_empty_steps(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(steps=[]))
        assert exc.value.code == "EMPTY_STEPS"

    def test_register_duplicate_step_id(self) -> None:
        dup_steps = [self._step(step_id="s1"), self._step(step_id="s1")]
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(steps=dup_steps))
        assert exc.value.code == "DUPLICATE_STEP_ID"

    def test_register_invalid_method_patch(self) -> None:
        # PATCH 是合法的
        p = self.eng.register(self._mk(steps=[self._step(method="PATCH")]))
        assert p.steps[0].method == "PATCH"

    def test_register_invalid_method_bad(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(steps=[self._step(method="OPTIONS")]))
        assert exc.value.code == "INVALID_METHOD"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_filter_status(self) -> None:
        self.eng.register(self._mk(name="a", status="active"))
        self.eng.register(self._mk(name="b", status="disabled"))
        assert len(self.eng.list(status="active")) == 1

    def test_update(self) -> None:
        p = self.eng.register(self._mk())
        updated = self.eng.update(p.id, {"name": "new-name", "status": "active"})
        assert updated.name == "new-name"
        assert updated.status == "active"

    def test_delete(self) -> None:
        p = self.eng.register(self._mk())
        assert self.eng.delete(p.id) is True
        assert self.eng.delete(p.id) is False

    def test_add_step(self) -> None:
        p = self.eng.register(self._mk())
        new_step = self._step(step_id="step-3", name="third step")
        updated = self.eng.add_step(p.id, new_step)
        assert len(updated.steps) == 3
        assert updated.steps[-1].step_id == "step-3"

    def test_remove_step(self) -> None:
        p = self.eng.register(self._mk())
        updated = self.eng.remove_step(p.id, "step-1")
        assert len(updated.steps) == 1
        assert updated.steps[0].step_id == "step-2"

    def test_remove_step_not_found(self) -> None:
        p = self.eng.register(self._mk())
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.remove_step(p.id, "nonexistent")
        assert exc.value.code == "STEP_NOT_FOUND"

    def test_reorder_steps(self) -> None:
        p = self.eng.register(self._mk())
        reordered = self.eng.reorder_steps(p.id, ["step-2", "step-1"])
        assert reordered.steps[0].step_id == "step-2"
        assert reordered.steps[1].step_id == "step-1"

    def test_run_success(self) -> None:
        p = self.eng.register(self._mk())
        run = self.eng.run(p.id, {"input_key": "input_val"})
        assert run.status == "completed"
        assert len(run.step_results) == 2
        assert run.current_step == 1
        assert "result" in run.outputs

    def test_run_disabled(self) -> None:
        p = self.eng.register(self._mk(status="disabled"))
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.run(p.id, {})
        assert exc.value.code == "PIPELINE_DISABLED"

    def test_list_runs_reverse_order(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.run(p.id, {"a": 1})
        self.eng.run(p.id, {"b": 2})
        runs = self.eng.list_runs(p.id)
        assert len(runs) == 2
        assert runs[0].started_at >= runs[1].started_at

    def test_get_run(self) -> None:
        p = self.eng.register(self._mk())
        run = self.eng.run(p.id, {"x": "y"})
        fetched = self.eng.get_run(run.run_id)
        assert fetched.run_id == run.run_id
        assert fetched.status == "completed"

    def test_get_run_not_found(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.get_run("nonexistent")
        assert exc.value.code == "RUN_NOT_FOUND"

    def test_max_pipelines_eviction(self) -> None:
        from aos_api.data_connection_webhook import _MAX_PIPELINES
        step = self._step(step_id="s1")
        for i in range(_MAX_PIPELINES + 5):
            self.eng.register(WebhookPipeline(name=f"p-{i}", steps=[step]))
        assert len(self.eng._pipelines) == _MAX_PIPELINES


# ════════════════════ WebhookOutputEngine ════════════════════

class TestWebhookOutput:
    def setup_method(self) -> None:
        self.eng = WebhookOutputEngine.__new__(WebhookOutputEngine)
        self.eng._configs = {}
        self.eng._lock = threading.Lock()

    def _field(self, **kw: object) -> OutputFieldMapping:
        defaults: dict[str, object] = {
            "field_id": "f1",
            "source_path": "data.userId",
            "target_name": "user_id",
            "target_type": "string",
        }
        defaults.update(kw)
        return OutputFieldMapping(**defaults)

    def _mk(self, **kw: object) -> WebhookOutputConfig:
        defaults: dict[str, object] = {
            "name": "user-output",
            "webhook_id": "wh-123",
            "output_fields": [
                self._field(field_id="f1", source_path="data.userId", target_name="user_id"),
                self._field(field_id="f2", source_path="data.score", target_name="score", target_type="integer"),
            ],
            "response_code_field": "code",
            "success_codes": ["0", "200"],
            "error_message_field": "message",
        }
        defaults.update(kw)
        return WebhookOutputConfig(**defaults)

    def test_register_returns_with_id(self) -> None:
        c = self.eng.register(self._mk())
        assert c.id.startswith("woc-")
        assert len(c.output_fields) == 2

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_missing_webhook(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(webhook_id=""))
        assert exc.value.code == "MISSING_WEBHOOK"

    def test_register_duplicate_field_id(self) -> None:
        fields = [self._field(field_id="f1"), self._field(field_id="f1", source_path="data.x")]
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(output_fields=fields))
        assert exc.value.code == "DUPLICATE_FIELD_ID"

    def test_register_invalid_target_type(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(output_fields=[self._field(target_type="array")]))
        assert exc.value.code == "INVALID_TARGET_TYPE"

    def test_register_invalid_source_path(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.register(self._mk(output_fields=[self._field(source_path="")]))
        assert exc.value.code == "INVALID_SOURCE_PATH"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_filter_webhook_id(self) -> None:
        self.eng.register(self._mk(name="a", webhook_id="wh-1"))
        self.eng.register(self._mk(name="b", webhook_id="wh-2"))
        assert len(self.eng.list(webhook_id="wh-1")) == 1

    def test_update(self) -> None:
        c = self.eng.register(self._mk())
        updated = self.eng.update(c.id, {"name": "new-name", "response_code_field": "status"})
        assert updated.name == "new-name"
        assert updated.response_code_field == "status"

    def test_delete(self) -> None:
        c = self.eng.register(self._mk())
        assert self.eng.delete(c.id) is True
        assert self.eng.delete(c.id) is False

    def test_add_field(self) -> None:
        c = self.eng.register(self._mk())
        new_field = self._field(field_id="f3", source_path="data.email", target_name="email")
        updated = self.eng.add_field(c.id, new_field)
        assert len(updated.output_fields) == 3

    def test_remove_field(self) -> None:
        c = self.eng.register(self._mk())
        updated = self.eng.remove_field(c.id, "f1")
        assert len(updated.output_fields) == 1
        assert updated.output_fields[0].field_id == "f2"

    def test_remove_field_not_found(self) -> None:
        c = self.eng.register(self._mk())
        with pytest.raises(DataConnectionWebhookError) as exc:
            self.eng.remove_field(c.id, "nonexistent")
        assert exc.value.code == "FIELD_NOT_FOUND"

    def test_extract_success(self) -> None:
        c = self.eng.register(self._mk())
        response = {"code": "0", "data": {"userId": "u123", "score": "95"}}
        result = self.eng.extract(c.id, response)
        assert result.success is True
        assert result.fields["user_id"] == "u123"
        assert result.fields["score"] == 95
        assert len(result.missing_required) == 0

    def test_extract_type_conversion_integer(self) -> None:
        c = self.eng.register(self._mk(output_fields=[
            self._field(field_id="f1", source_path="val", target_name="val", target_type="integer"),
        ]))
        result = self.eng.extract(c.id, {"val": "42"})
        assert result.fields["val"] == 42

    def test_extract_type_conversion_boolean(self) -> None:
        c = self.eng.register(self._mk(output_fields=[
            self._field(field_id="f1", source_path="flag", target_name="flag", target_type="boolean"),
        ]))
        result = self.eng.extract(c.id, {"flag": "true"})
        assert result.fields["flag"] is True

    def test_extract_missing_required(self) -> None:
        c = self.eng.register(self._mk(output_fields=[
            self._field(field_id="f1", source_path="data.missing", target_name="required_val", required=True),
        ]))
        result = self.eng.extract(c.id, {"data": {}})
        assert result.success is False
        assert "required_val" in result.missing_required

    def test_validate_response_success(self) -> None:
        c = self.eng.register(self._mk())
        result = self.eng.validate_response(c.id, {"code": "0", "message": "ok"})
        assert result["valid"] is True
        assert result["code"] == "0"

    def test_validate_response_failure(self) -> None:
        c = self.eng.register(self._mk())
        result = self.eng.validate_response(c.id, {"code": "500", "message": "server error"})
        assert result["valid"] is False
        assert result["message"] == "server error"

    def test_max_configs_eviction(self) -> None:
        from aos_api.data_connection_webhook import _MAX_OUTPUT_CONFIGS
        for i in range(_MAX_OUTPUT_CONFIGS + 5):
            self.eng.register(WebhookOutputConfig(name=f"c-{i}", webhook_id=f"w-{i}"))
        assert len(self.eng._configs) == _MAX_OUTPUT_CONFIGS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_stream_export_singleton(self) -> None:
        a = get_stream_export_engine()
        b = get_stream_export_engine()
        assert a is b

    def test_webhook_pipeline_singleton(self) -> None:
        a = get_webhook_pipeline_engine()
        b = get_webhook_pipeline_engine()
        assert a is b

    def test_webhook_output_singleton(self) -> None:
        a = get_webhook_output_engine()
        b = get_webhook_output_engine()
        assert a is b
