"""Pipeline Types 补充测试：#97 Compute Profile + #98 Streaming Performance。

覆盖 L1065 计算选项（Standard/Faster/External）和 L1070 流式性能考量（背压/资源/容错）。
"""
from __future__ import annotations

import pytest

from aos_api.pipeline_type_semantics import (
    ComputeProfileSpec,
    PipelineTypeError,
    StreamingPerfConfig,
    BackpressurePolicy,
    ResourceLimit,
    FaultToleranceSpec,
    get_compute_profile_engine,
    get_streaming_perf_engine,
)


# ════════════════════ #97 Compute Profile ════════════════════

class TestComputeProfileEngine:
    """计算选项引擎测试。"""

    def setup_method(self):
        self.engine = get_compute_profile_engine()

    def test_list_default_profiles(self):
        """应返回 3 个默认配置。"""
        items = self.engine.list()
        profiles = {s.profile for s in items}
        assert profiles == {"standard", "faster", "external"}

    def test_get_standard_profile(self):
        """standard 配置应有合理的资源。"""
        s = self.engine.get("standard")
        assert s.driver_cores >= 1.0
        assert s.executor_memory_mb >= 4096
        assert s.external_endpoint == ""

    def test_get_faster_profile(self):
        """faster 配置应有更多资源。"""
        s = self.engine.get("faster")
        std = self.engine.get("standard")
        assert s.executor_cores > std.executor_cores
        assert s.auto_scale is True

    def test_get_external_profile(self):
        """external 配置应有端点。"""
        s = self.engine.get("external")
        assert s.external_endpoint != ""
        assert s.driver_cores == 0

    def test_get_nonexistent_profile_raises(self):
        with pytest.raises(PipelineTypeError) as exc:
            self.engine.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_register_custom_profile(self):
        """注册新的 standard 变体。"""
        spec = ComputeProfileSpec(
            profile="standard",
            description="自定义标准配置",
            driver_cores=4.0,
            executor_count=8,
        )
        result = self.engine.register(spec)
        assert result.driver_cores == 4.0
        assert result.executor_count == 8

    def test_register_invalid_profile_raises(self):
        spec = ComputeProfileSpec(profile="turbo", description="x")
        with pytest.raises(PipelineTypeError) as exc:
            self.engine.register(spec)
        assert exc.value.code == "INVALID_PROFILE"

    def test_update_profile(self):
        result = self.engine.update("standard", {"executor_count": 16})
        assert result.executor_count == 16

    def test_update_immutable_profile_field(self):
        with pytest.raises(PipelineTypeError) as exc:
            self.engine.update("standard", {"profile": "external"})
        assert exc.value.code == "IMMUTABLE_FIELD"

    def test_assign_profile_to_pipeline(self):
        result = self.engine.assign("pipe-1", "faster")
        assert result["pipeline_id"] == "pipe-1"
        assert result["profile"] == "faster"
        assert result["spec"] is not None

    def test_get_assignment(self):
        self.engine.assign("pipe-2", "standard")
        result = self.engine.get_assignment("pipe-2")
        assert result["profile"] == "standard"

    def test_get_assignment_unset_returns_none(self):
        result = self.engine.get_assignment("never-assigned")
        assert result["profile"] is None

    def test_estimate_cost_standard(self):
        result = self.engine.estimate_cost("standard", 60.0)
        assert result["duration_minutes"] == 60.0
        assert result["estimated_cost"] > 0
        assert result["currency"] == "CNY"

    def test_estimate_cost_external(self):
        result = self.engine.estimate_cost("external", 60.0)
        assert result["estimated_cost"] > 0

    def test_estimate_cost_faster_more_expensive(self):
        std_cost = self.engine.estimate_cost("standard", 60.0)["estimated_cost"]
        faster_cost = self.engine.estimate_cost("faster", 60.0)["estimated_cost"]
        assert faster_cost > std_cost

    def test_register_external_without_endpoint_raises(self):
        spec = ComputeProfileSpec(
            profile="external", description="x", external_endpoint="",
        )
        with pytest.raises(PipelineTypeError) as exc:
            self.engine.register(spec)
        assert exc.value.code == "MISSING_ENDPOINT"


# ════════════════════ #98 Streaming Performance ════════════════════

class TestStreamingPerfEngine:
    """流式性能 / 容错引擎测试。"""

    def setup_method(self):
        self.engine = get_streaming_perf_engine()

    def test_get_default_config(self):
        """未配置的管道返回默认配置。"""
        cfg = self.engine.get_config("pipe-default")
        assert cfg.pipeline_id == "pipe-default"
        assert cfg.backpressure.strategy == "buffer"
        assert cfg.fault.level == "at_least_once"

    def test_set_config(self):
        cfg = StreamingPerfConfig(
            pipeline_id="pipe-perf-1",
            backpressure=BackpressurePolicy(strategy="block", buffer_size=5000),
            resource=ResourceLimit(max_in_flight=2000, max_parallelism=8),
            fault=FaultToleranceSpec(level="exactly_once", max_retries=5),
        )
        result = self.engine.set_config(cfg)
        assert result.backpressure.strategy == "block"
        assert result.resource.max_parallelism == 8
        assert result.fault.level == "exactly_once"

    def test_set_config_invalid_backpressure(self):
        cfg = StreamingPerfConfig(
            pipeline_id="pipe-invalid-bp",
            backpressure=BackpressurePolicy(strategy="invalid"),
        )
        with pytest.raises(PipelineTypeError) as exc:
            self.engine.set_config(cfg)
        assert exc.value.code == "INVALID_BACKPRESSURE"

    def test_set_config_invalid_fault_level(self):
        cfg = StreamingPerfConfig(
            pipeline_id="pipe-invalid-ft",
            fault=FaultToleranceSpec(level="invalid"),
        )
        with pytest.raises(PipelineTypeError) as exc:
            self.engine.set_config(cfg)
        assert exc.value.code == "INVALID_FAULT_LEVEL"

    def test_set_config_invalid_parallelism(self):
        cfg = StreamingPerfConfig(
            pipeline_id="pipe-invalid-par",
            resource=ResourceLimit(max_parallelism=0),
        )
        with pytest.raises(PipelineTypeError) as exc:
            self.engine.set_config(cfg)
        assert exc.value.code == "INVALID_PARALLELISM"

    def test_check_backpressure_normal(self):
        """低于 low_watermark 时为 normal。"""
        self.engine.set_config(StreamingPerfConfig(
            pipeline_id="pipe-bp-normal",
            backpressure=BackpressurePolicy(
                strategy="buffer", buffer_size=10000,
                high_watermark_pct=80.0, low_watermark_pct=50.0,
            ),
        ))
        result = self.engine.check_backpressure("pipe-bp-normal", 1000)
        assert result["action"] == "normal"
        assert result["should_throttle"] is False

    def test_check_backpressure_warn(self):
        """buffer 策略在高水位时为 warn。"""
        self.engine.set_config(StreamingPerfConfig(
            pipeline_id="pipe-bp-warn",
            backpressure=BackpressurePolicy(
                strategy="buffer", buffer_size=10000,
                high_watermark_pct=80.0,
            ),
        ))
        result = self.engine.check_backpressure("pipe-bp-warn", 8500)
        assert result["action"] == "warn"
        assert result["should_throttle"] is True

    def test_check_backpressure_drop(self):
        """drop_oldest 策略在高水位时为 drop。"""
        self.engine.set_config(StreamingPerfConfig(
            pipeline_id="pipe-bp-drop",
            backpressure=BackpressurePolicy(strategy="drop_oldest"),
        ))
        result = self.engine.check_backpressure("pipe-bp-drop", 9000)
        assert result["action"] == "drop"

    def test_check_backpressure_block(self):
        """block 策略在高水位时为 block。"""
        self.engine.set_config(StreamingPerfConfig(
            pipeline_id="pipe-bp-block",
            backpressure=BackpressurePolicy(strategy="block"),
        ))
        result = self.engine.check_backpressure("pipe-bp-block", 9500)
        assert result["action"] == "block"

    def test_record_load(self):
        result = self.engine.record_load("pipe-load", 100)
        assert result["in_flight"] == 100
        assert result["overloaded"] is False
        # 减少负载
        result2 = self.engine.record_load("pipe-load", -50)
        assert result2["in_flight"] == 50

    def test_record_load_overloaded(self):
        self.engine.set_config(StreamingPerfConfig(
            pipeline_id="pipe-overload",
            resource=ResourceLimit(max_in_flight=10),
        ))
        result = self.engine.record_load("pipe-overload", 10)
        assert result["overloaded"] is True

    def test_send_and_list_dlq(self):
        self.engine.send_to_dlq(
            "pipe-dlq", {"event_id": "e1"}, "processing_failed",
        )
        self.engine.send_to_dlq(
            "pipe-dlq", {"event_id": "e2"}, "timeout",
        )
        items = self.engine.list_dlq("pipe-dlq")
        assert len(items) >= 2
        assert items[-1]["reason"] == "timeout"

    def test_get_health(self):
        self.engine.set_config(StreamingPerfConfig(
            pipeline_id="pipe-health",
            resource=ResourceLimit(max_in_flight=100),
        ))
        self.engine.record_load("pipe-health", 50)
        health = self.engine.get_health("pipe-health")
        assert health["in_flight"] == 50
        assert health["max_in_flight"] == 100
        assert health["status"] == "healthy"

    def test_get_health_stressed(self):
        self.engine.set_config(StreamingPerfConfig(
            pipeline_id="pipe-stressed",
            resource=ResourceLimit(max_in_flight=100),
        ))
        self.engine.record_load("pipe-stressed", 85)
        health = self.engine.get_health("pipe-stressed")
        assert health["status"] == "stressed"

    def test_get_health_overloaded(self):
        self.engine.set_config(StreamingPerfConfig(
            pipeline_id="pipe-over",
            resource=ResourceLimit(max_in_flight=100),
        ))
        self.engine.record_load("pipe-over", 100)
        health = self.engine.get_health("pipe-over")
        assert health["status"] == "overloaded"
