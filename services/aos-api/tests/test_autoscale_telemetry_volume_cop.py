"""W2-BN · Autoscale / Telemetry / Volume / COP 引擎组单元测试（#22 #23 #24 #25）.

覆盖：
- PredictiveAutoscaleEngine（#22 预测扩缩）
- TelemetryFormatEngine（#23 Telemetry / Format / Container log source）
- VolumeMountEngine（#24 Volume mounts 副本内共享卷）
- CopRealtimeEngine（#25 COP 实时态势）
"""
from __future__ import annotations

import time

import pytest

from aos_api.autoscale_telemetry_volume_cop import (
    AutoscaleTelemetryError,
    CopAlert,
    CopMetric,
    CopRealtimeEngine,
    LoadPrediction,
    LogSource,
    PredictiveAutoscaleEngine,
    TelemetryConfig,
    TelemetryFormatEngine,
    VolumeAttachment,
    VolumeMount,
    VolumeMountEngine,
    WarmupSchedule,
    get_cop_realtime_engine,
    get_predictive_autoscale_engine,
    get_telemetry_format_engine,
    get_volume_mount_engine,
)


# ════════════════════ #22 PredictiveAutoscaleEngine ════════════════════


class TestPredictiveAutoscaleEngine:
    def setup_method(self) -> None:
        self.engine = PredictiveAutoscaleEngine()

    # --- record_prediction: scale_up ---
    def test_record_prediction_scale_up(self) -> None:
        pred = self.engine.record_prediction(
            resource_id="res-1",
            predicted_load=0.9,
            target_time=time.time() + 60,
            confidence=0.8,
            reason="peak hour",
        )
        assert pred.action == "scale_up"
        assert pred.resource_id == "res-1"
        assert pred.predicted_load == 0.9
        assert pred.confidence == 0.8
        assert pred.reason == "peak hour"
        assert pred.id.startswith("pred-")

    # --- record_prediction: scale_down ---
    def test_record_prediction_scale_down(self) -> None:
        pred = self.engine.record_prediction(
            resource_id="res-1",
            predicted_load=0.2,
            target_time=time.time() + 60,
        )
        assert pred.action == "scale_down"

    # --- record_prediction: no_action ---
    def test_record_prediction_no_action(self) -> None:
        # 0.3 <= load <= 0.8 → no_action（边界值 0.3 / 0.8 均为 no_action）
        for load in (0.3, 0.5, 0.8):
            pred = self.engine.record_prediction(
                resource_id="res-1",
                predicted_load=load,
                target_time=time.time() + 60,
            )
            assert pred.action == "no_action", f"load={load} 应为 no_action"

    # --- get_prediction ---
    def test_get_prediction(self) -> None:
        pred = self.engine.record_prediction(
            resource_id="res-1",
            predicted_load=0.5,
            target_time=time.time() + 60,
        )
        got = self.engine.get_prediction(pred.id)
        assert got.id == pred.id
        assert got.resource_id == "res-1"

    # --- get_prediction not found ---
    def test_get_prediction_not_found(self) -> None:
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.get_prediction("pred-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    # --- list_predictions: filter by resource_id / action ---
    def test_list_predictions(self) -> None:
        self.engine.record_prediction(
            resource_id="res-1", predicted_load=0.9, target_time=time.time() + 60
        )
        self.engine.record_prediction(
            resource_id="res-1", predicted_load=0.2, target_time=time.time() + 60
        )
        self.engine.record_prediction(
            resource_id="res-2", predicted_load=0.9, target_time=time.time() + 60
        )
        # 全量
        all_preds = self.engine.list_predictions()
        assert len(all_preds) == 3
        # 按 resource_id 过滤
        res1 = self.engine.list_predictions(resource_id="res-1")
        assert len(res1) == 2
        assert all(p.resource_id == "res-1" for p in res1)
        # 按 action 过滤
        ups = self.engine.list_predictions(action="scale_up")
        assert len(ups) == 2
        assert all(p.action == "scale_up" for p in ups)
        # 组合过滤
        combo = self.engine.list_predictions(resource_id="res-2", action="scale_up")
        assert len(combo) == 1
        # 结果按 prediction_time 排序
        assert all(
            all_preds[i].prediction_time <= all_preds[i + 1].prediction_time
            for i in range(len(all_preds) - 1)
        )

    # --- delete_prediction ---
    def test_delete_prediction(self) -> None:
        pred = self.engine.record_prediction(
            resource_id="res-1", predicted_load=0.5, target_time=time.time() + 60
        )
        assert self.engine.delete_prediction(pred.id) is True
        # 再次删除返回 False
        assert self.engine.delete_prediction(pred.id) is False
        with pytest.raises(AutoscaleTelemetryError):
            self.engine.get_prediction(pred.id)

    # --- schedule_warmup ---
    def test_schedule_warmup(self) -> None:
        warmup = self.engine.schedule_warmup(
            resource_id="res-1",
            target_replicas=3,
            warmup_time=time.time() + 120,
        )
        assert warmup.id.startswith("warm-")
        assert warmup.resource_id == "res-1"
        assert warmup.target_replicas == 3
        assert warmup.status == "scheduled"

    # --- schedule_warmup: invalid replicas ---
    def test_schedule_warmup_invalid_replicas(self) -> None:
        for bad in (0, -1):
            with pytest.raises(AutoscaleTelemetryError) as exc_info:
                self.engine.schedule_warmup(
                    resource_id="res-1",
                    target_replicas=bad,
                    warmup_time=time.time() + 120,
                )
            assert exc_info.value.code == "INVALID_REPLICAS"

    # --- execute_warmup ---
    def test_execute_warmup(self) -> None:
        warmup = self.engine.schedule_warmup(
            resource_id="res-1",
            target_replicas=3,
            warmup_time=time.time() + 120,
        )
        executed = self.engine.execute_warmup(warmup.id)
        assert executed.status == "executed"
        assert executed.id == warmup.id
        # 再次 execute 仍为 executed
        executed2 = self.engine.execute_warmup(warmup.id)
        assert executed2.status == "executed"

    # --- cancel_warmup ---
    def test_cancel_warmup(self) -> None:
        warmup = self.engine.schedule_warmup(
            resource_id="res-1",
            target_replicas=3,
            warmup_time=time.time() + 120,
        )
        cancelled = self.engine.cancel_warmup(warmup.id)
        assert cancelled.status == "cancelled"
        assert cancelled.id == warmup.id

    # --- cancel_warmup: already executed ---
    def test_cancel_warmup_already_executed(self) -> None:
        warmup = self.engine.schedule_warmup(
            resource_id="res-1",
            target_replicas=3,
            warmup_time=time.time() + 120,
        )
        self.engine.execute_warmup(warmup.id)
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.cancel_warmup(warmup.id)
        assert exc_info.value.code == "ALREADY_EXECUTED"
        # 已 cancelled 的也无法再次 cancel
        warmup2 = self.engine.schedule_warmup(
            resource_id="res-1",
            target_replicas=2,
            warmup_time=time.time() + 120,
        )
        self.engine.cancel_warmup(warmup2.id)
        with pytest.raises(AutoscaleTelemetryError) as exc_info2:
            self.engine.cancel_warmup(warmup2.id)
        assert exc_info2.value.code == "ALREADY_EXECUTED"

    # --- FIFO eviction for predictions ---
    def test_fifo_eviction_predictions(self) -> None:
        max_cap = PredictiveAutoscaleEngine._MAX_PREDICTIONS
        first = self.engine.record_prediction(
            resource_id="res-first", predicted_load=0.5, target_time=time.time() + 60
        )
        # 再插入到达到上限
        for i in range(max_cap):
            self.engine.record_prediction(
                resource_id=f"res-{i}",
                predicted_load=0.5,
                target_time=time.time() + 60,
            )
        # 总数应等于上限
        assert len(self.engine.list_predictions()) == max_cap
        # 最早一条应被淘汰
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.get_prediction(first.id)
        assert exc_info.value.code == "NOT_FOUND"


# ════════════════════ #23 TelemetryFormatEngine ════════════════════


class TestTelemetryFormatEngine:
    def setup_method(self) -> None:
        self.engine = TelemetryFormatEngine()

    # --- set_config ---
    def test_set_config(self) -> None:
        config = self.engine.set_config(
            resource_id="res-1",
            enabled=True,
            format="otel",
            sample_rate=0.5,
            log_source="container",
            destinations=["dest-1", "dest-2"],
        )
        assert config.id.startswith("tel-")
        assert config.resource_id == "res-1"
        assert config.enabled is True
        assert config.format == "otel"
        assert config.sample_rate == 0.5
        assert config.log_source == "container"
        assert config.destinations == ["dest-1", "dest-2"]

    # --- set_config: invalid format ---
    def test_set_config_invalid_format(self) -> None:
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.set_config(resource_id="res-1", format="xml")
        assert exc_info.value.code == "INVALID_FORMAT"

    # --- set_config: invalid log_source ---
    def test_set_config_invalid_log_source(self) -> None:
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.set_config(resource_id="res-1", log_source="syslog")
        assert exc_info.value.code == "INVALID_LOG_SOURCE"

    # --- set_config: invalid sample_rate ---
    def test_set_config_invalid_sample_rate(self) -> None:
        for bad in (1.5, -0.1):
            with pytest.raises(AutoscaleTelemetryError) as exc_info:
                self.engine.set_config(resource_id="res-1", sample_rate=bad)
            assert exc_info.value.code == "INVALID_SAMPLE_RATE"
        # 边界值 0 与 1 合法
        for ok in (0.0, 1.0):
            cfg = self.engine.set_config(resource_id="res-1", sample_rate=ok)
            assert cfg.sample_rate == ok

    # --- get_config / list_configs / update_config / delete_config ---
    def test_config_crud(self) -> None:
        # get_config not found
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.get_config("res-missing")
        assert exc_info.value.code == "NOT_FOUND"

        self.engine.set_config(resource_id="res-1", format="json", enabled=True)
        self.engine.set_config(resource_id="res-2", format="otel", enabled=False)

        # get_config
        c1 = self.engine.get_config("res-1")
        assert c1.format == "json"
        assert c1.enabled is True

        # list_configs
        all_cfgs = self.engine.list_configs()
        assert len(all_cfgs) == 2
        enabled_only = self.engine.list_configs(enabled_only=True)
        assert len(enabled_only) == 1
        assert enabled_only[0].resource_id == "res-1"

        # update_config（更新同一 resource_id 保留 id/created_at）
        original = self.engine.get_config("res-1")
        updated = self.engine.update_config(
            "res-1", {"format": "plain", "enabled": False, "sample_rate": 0.25}
        )
        assert updated.format == "plain"
        assert updated.enabled is False
        assert updated.sample_rate == 0.25
        assert updated.id == original.id
        assert updated.created_at == original.created_at

        # update_config: 不存在
        with pytest.raises(AutoscaleTelemetryError) as exc_info2:
            self.engine.update_config("res-missing", {"format": "json"})
        assert exc_info2.value.code == "NOT_FOUND"

        # update_config: 非法字段校验
        with pytest.raises(AutoscaleTelemetryError) as exc_info3:
            self.engine.update_config("res-1", {"format": "xml"})
        assert exc_info3.value.code == "INVALID_FORMAT"

        # delete_config
        assert self.engine.delete_config("res-1") is True
        assert self.engine.delete_config("res-1") is False
        with pytest.raises(AutoscaleTelemetryError):
            self.engine.get_config("res-1")

    # --- register_source ---
    def test_register_source(self) -> None:
        source = self.engine.register_source(
            resource_id="res-1",
            source_type="file",
            path="/var/log/app.log",
            format="plain",
        )
        assert source.id.startswith("log-")
        assert source.resource_id == "res-1"
        assert source.source_type == "file"
        assert source.path == "/var/log/app.log"
        assert source.format == "plain"
        assert source.last_collected_at == 0

    # --- register_source: invalid type ---
    def test_register_source_invalid_type(self) -> None:
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.register_source(resource_id="res-1", source_type="syslog")
        assert exc_info.value.code == "INVALID_SOURCE_TYPE"

    # --- collect_from_source: sets last_collected_at ---
    def test_collect_from_source(self) -> None:
        source = self.engine.register_source(
            resource_id="res-1", source_type="stdout"
        )
        assert source.last_collected_at == 0
        collected = self.engine.collect_from_source(source.id)
        assert collected.last_collected_at > 0
        # 持久化到存储
        again = self.engine.get_source(source.id)
        assert again.last_collected_at == collected.last_collected_at
        # collect 不存在的 source
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.collect_from_source("log-missing")
        assert exc_info.value.code == "NOT_FOUND"

    # --- list_sources / delete_source ---
    def test_list_and_delete_sources(self) -> None:
        self.engine.register_source(resource_id="res-1", source_type="stdout")
        self.engine.register_source(resource_id="res-1", source_type="file")
        self.engine.register_source(resource_id="res-2", source_type="stdout")

        # list 全量
        all_srcs = self.engine.list_sources()
        assert len(all_srcs) == 3
        # 按 resource_id 过滤
        res1 = self.engine.list_sources(resource_id="res-1")
        assert len(res1) == 2
        # 按 source_type 过滤
        stdouts = self.engine.list_sources(source_type="stdout")
        assert len(stdouts) == 2
        # 组合过滤
        combo = self.engine.list_sources(resource_id="res-2", source_type="stdout")
        assert len(combo) == 1
        # 结果按 created_at 排序
        assert all(
            all_srcs[i].created_at <= all_srcs[i + 1].created_at
            for i in range(len(all_srcs) - 1)
        )

        # delete
        target = all_srcs[0]
        assert self.engine.delete_source(target.id) is True
        assert self.engine.delete_source(target.id) is False
        assert len(self.engine.list_sources()) == 2


# ════════════════════ #24 VolumeMountEngine ════════════════════


class TestVolumeMountEngine:
    def setup_method(self) -> None:
        self.engine = VolumeMountEngine()

    # --- create_volume ---
    def test_create_volume(self) -> None:
        vol = self.engine.create_volume(
            name="data-vol",
            mount_path="/data",
            storage_type="pvc",
            size_gb=10.5,
            read_only=False,
            shared=True,
            access_mode="readwrite",
        )
        assert vol.id.startswith("vol-")
        assert vol.name == "data-vol"
        assert vol.mount_path == "/data"
        assert vol.storage_type == "pvc"
        assert vol.size_gb == 10.5
        assert vol.read_only is False
        assert vol.shared is True
        assert vol.access_mode == "readwrite"

    # --- create_volume: invalid storage_type ---
    def test_create_volume_invalid_storage_type(self) -> None:
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.create_volume(
                name="v", mount_path="/d", storage_type="nfs"
            )
        assert exc_info.value.code == "INVALID_STORAGE_TYPE"

    # --- create_volume: invalid access_mode ---
    def test_create_volume_invalid_access_mode(self) -> None:
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.create_volume(
                name="v", mount_path="/d", access_mode="writeonly"
            )
        assert exc_info.value.code == "INVALID_ACCESS_MODE"

    # --- get_volume / list_volumes: filter by storage_type, shared_only ---
    def test_get_and_list_volumes(self) -> None:
        # get not found
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.get_volume("vol-missing")
        assert exc_info.value.code == "NOT_FOUND"

        v1 = self.engine.create_volume(
            name="v1", mount_path="/d1", storage_type="pvc", shared=True
        )
        v2 = self.engine.create_volume(
            name="v2", mount_path="/d2", storage_type="emptydir", shared=False
        )

        # get_volume
        got = self.engine.get_volume(v1.id)
        assert got.id == v1.id

        # list 全量
        all_vols = self.engine.list_volumes()
        assert len(all_vols) == 2
        # 按 storage_type 过滤
        pvcs = self.engine.list_volumes(storage_type="pvc")
        assert len(pvcs) == 1
        assert pvcs[0].id == v1.id
        # shared_only
        shared = self.engine.list_volumes(shared_only=True)
        assert len(shared) == 1
        assert shared[0].id == v1.id
        # 组合
        combo = self.engine.list_volumes(storage_type="emptydir", shared_only=True)
        assert len(combo) == 0
        # 排序
        assert all(
            all_vols[i].created_at <= all_vols[i + 1].created_at
            for i in range(len(all_vols) - 1)
        )

    # --- update_volume / delete_volume ---
    def test_update_and_delete_volume(self) -> None:
        vol = self.engine.create_volume(name="v", mount_path="/d", storage_type="pvc")
        updated = self.engine.update_volume(
            vol.id, {"size_gb": 20.0, "shared": True, "read_only": True}
        )
        assert updated.size_gb == 20.0
        assert updated.shared is True
        assert updated.read_only is True
        assert updated.id == vol.id

        # update: 不存在
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.update_volume("vol-missing", {"size_gb": 1.0})
        assert exc_info.value.code == "NOT_FOUND"

        # update: 非法 storage_type
        with pytest.raises(AutoscaleTelemetryError) as exc_info2:
            self.engine.update_volume(vol.id, {"storage_type": "nfs"})
        assert exc_info2.value.code == "INVALID_STORAGE_TYPE"

        # update: 非法 access_mode
        with pytest.raises(AutoscaleTelemetryError) as exc_info3:
            self.engine.update_volume(vol.id, {"access_mode": "writeonly"})
        assert exc_info3.value.code == "INVALID_ACCESS_MODE"

        # delete
        assert self.engine.delete_volume(vol.id) is True
        assert self.engine.delete_volume(vol.id) is False
        with pytest.raises(AutoscaleTelemetryError):
            self.engine.get_volume(vol.id)

    # --- attach_volume / get_attachment / list_attachments ---
    def test_attach_get_list_attachments(self) -> None:
        # attach 不存在的 volume
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.attach_volume(volume_id="vol-missing", target_id="t-1")
        assert exc_info.value.code == "NOT_FOUND"

        vol = self.engine.create_volume(name="v", mount_path="/d", storage_type="pvc")
        att = self.engine.attach_volume(
            volume_id=vol.id,
            target_id="t-1",
            sub_path="cfg",
            mount_path="/etc/cfg",
            read_only=True,
        )
        assert att.id.startswith("att-")
        assert att.volume_id == vol.id
        assert att.target_id == "t-1"
        assert att.sub_path == "cfg"
        assert att.mount_path == "/etc/cfg"
        assert att.read_only is True

        # get not found
        with pytest.raises(AutoscaleTelemetryError) as exc_info2:
            self.engine.get_attachment("att-missing")
        assert exc_info2.value.code == "NOT_FOUND"

        # get
        got = self.engine.get_attachment(att.id)
        assert got.id == att.id

        # 再挂载一个到不同 target
        att2 = self.engine.attach_volume(volume_id=vol.id, target_id="t-2")

        # list 全量
        all_atts = self.engine.list_attachments()
        assert len(all_atts) == 2
        # 按 volume_id 过滤
        by_vol = self.engine.list_attachments(volume_id=vol.id)
        assert len(by_vol) == 2
        # 按 target_id 过滤
        by_target = self.engine.list_attachments(target_id="t-1")
        assert len(by_target) == 1
        assert by_target[0].id == att.id
        # 排序
        assert all(
            all_atts[i].created_at <= all_atts[i + 1].created_at
            for i in range(len(all_atts) - 1)
        )

    # --- detach_volume ---
    def test_detach_volume(self) -> None:
        vol = self.engine.create_volume(name="v", mount_path="/d", storage_type="pvc")
        att = self.engine.attach_volume(volume_id=vol.id, target_id="t-1")
        assert self.engine.detach_volume(att.id) is True
        # 再次 detach 返回 False
        assert self.engine.detach_volume(att.id) is False
        with pytest.raises(AutoscaleTelemetryError):
            self.engine.get_attachment(att.id)

    # --- get_shared_volumes ---
    def test_get_shared_volumes(self) -> None:
        v1 = self.engine.create_volume(name="v1", mount_path="/d1", shared=True)
        v2 = self.engine.create_volume(name="v2", mount_path="/d2", shared=False)
        v3 = self.engine.create_volume(name="v3", mount_path="/d3", shared=True)
        shared = self.engine.get_shared_volumes()
        assert {v.id for v in shared} == {v1.id, v3.id}
        # 排序
        assert all(
            shared[i].created_at <= shared[i + 1].created_at
            for i in range(len(shared) - 1)
        )

    # --- FIFO eviction for volumes ---
    def test_fifo_eviction_volumes(self) -> None:
        max_cap = VolumeMountEngine._MAX_VOLUMES
        first = self.engine.create_volume(name="first", mount_path="/f")
        for i in range(max_cap):
            self.engine.create_volume(name=f"v-{i}", mount_path=f"/d-{i}")
        assert len(self.engine.list_volumes()) == max_cap
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.get_volume(first.id)
        assert exc_info.value.code == "NOT_FOUND"


# ════════════════════ #25 CopRealtimeEngine ════════════════════


class TestCopRealtimeEngine:
    def setup_method(self) -> None:
        self.engine = CopRealtimeEngine()

    # --- set_threshold ---
    def test_set_threshold(self) -> None:
        result = self.engine.set_threshold(
            resource_id="res-1",
            metric_name="cpu",
            warning=50.0,
            critical=80.0,
        )
        assert result == {
            "resource_id": "res-1",
            "metric_name": "cpu",
            "warning": 50.0,
            "critical": 80.0,
        }

    # --- set_threshold: invalid ---
    def test_set_threshold_invalid(self) -> None:
        # warning >= critical → error
        for warn, crit in ((80.0, 80.0), (90.0, 80.0)):
            with pytest.raises(AutoscaleTelemetryError) as exc_info:
                self.engine.set_threshold(
                    resource_id="res-1", metric_name="cpu",
                    warning=warn, critical=crit,
                )
            assert exc_info.value.code == "INVALID_THRESHOLD"

    # --- get_thresholds: filter by resource_id ---
    def test_get_thresholds(self) -> None:
        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        self.engine.set_threshold("res-1", "mem", 60.0, 90.0)
        self.engine.set_threshold("res-2", "cpu", 40.0, 70.0)

        # 全量
        all_th = self.engine.get_thresholds()
        assert len(all_th) == 3
        # 按 resource_id 过滤
        res1 = self.engine.get_thresholds(resource_id="res-1")
        assert len(res1) == 2
        assert all(t["resource_id"] == "res-1" for t in res1)
        # 过滤不存在的 resource_id
        assert self.engine.get_thresholds(resource_id="res-missing") == []

    # --- delete_threshold ---
    def test_delete_threshold(self) -> None:
        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        assert self.engine.delete_threshold("res-1", "cpu") is True
        # 再次删除返回 False
        assert self.engine.delete_threshold("res-1", "cpu") is False
        assert self.engine.get_thresholds(resource_id="res-1") == []

    # --- record_metric: normal (below warning) ---
    def test_record_metric_normal(self) -> None:
        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        metric = self.engine.record_metric(
            resource_id="res-1",
            metric_name="cpu",
            value=30.0,
            unit="%",
            metadata={"host": "h1"},
        )
        assert metric.id.startswith("cop-")
        assert metric.resource_id == "res-1"
        assert metric.metric_name == "cpu"
        assert metric.value == 30.0
        assert metric.unit == "%"
        assert metric.severity == "normal"
        assert metric.metadata == {"host": "h1"}
        # normal 不创建 alert
        assert self.engine.list_alerts() == []

    # --- record_metric: warning ---
    def test_record_metric_warning(self) -> None:
        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        metric = self.engine.record_metric(
            resource_id="res-1", metric_name="cpu", value=60.0, unit="%"
        )
        assert metric.severity == "warning"
        # warning 创建一条 alert
        alerts = self.engine.list_alerts()
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.id.startswith("copalert-")
        assert alert.metric_id == metric.id
        assert alert.resource_id == "res-1"
        assert alert.metric_name == "cpu"
        assert alert.value == 60.0
        assert alert.threshold == 50.0
        assert alert.severity == "warning"
        assert alert.acknowledged is False
        # 边界：value == warning 也算 warning
        m2 = self.engine.record_metric(
            resource_id="res-1", metric_name="cpu", value=50.0
        )
        assert m2.severity == "warning"

    # --- record_metric: critical ---
    def test_record_metric_critical(self) -> None:
        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        metric = self.engine.record_metric(
            resource_id="res-1", metric_name="cpu", value=90.0, unit="%"
        )
        assert metric.severity == "critical"
        alerts = self.engine.list_alerts()
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.severity == "critical"
        assert alert.threshold == 80.0
        assert alert.metric_id == metric.id
        # 边界：value == critical 也算 critical
        m2 = self.engine.record_metric(
            resource_id="res-1", metric_name="cpu", value=80.0
        )
        assert m2.severity == "critical"

    # --- record_metric: 无阈值时为 normal ---
    def test_record_metric_no_threshold(self) -> None:
        metric = self.engine.record_metric(
            resource_id="res-1", metric_name="cpu", value=999.0
        )
        assert metric.severity == "normal"
        assert self.engine.list_alerts() == []

    # --- get_metric / list_metrics: filter by resource_id, severity ---
    def test_get_and_list_metrics(self) -> None:
        # get not found
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.get_metric("cop-missing")
        assert exc_info.value.code == "NOT_FOUND"

        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        self.engine.set_threshold("res-2", "cpu", 50.0, 80.0)
        m_normal = self.engine.record_metric("res-1", "cpu", 30.0)
        m_warn = self.engine.record_metric("res-1", "cpu", 60.0)
        self.engine.record_metric("res-2", "cpu", 60.0)

        # get
        got = self.engine.get_metric(m_normal.id)
        assert got.id == m_normal.id

        # list 全量
        all_m = self.engine.list_metrics()
        assert len(all_m) == 3
        # 按 resource_id 过滤
        res1 = self.engine.list_metrics(resource_id="res-1")
        assert len(res1) == 2
        assert all(m.resource_id == "res-1" for m in res1)
        # 按 severity 过滤
        warnings = self.engine.list_metrics(severity="warning")
        assert len(warnings) == 2
        assert all(m.severity == "warning" for m in warnings)
        # 组合过滤
        combo = self.engine.list_metrics(resource_id="res-1", severity="warning")
        assert len(combo) == 1
        assert combo[0].id == m_warn.id
        # 排序
        assert all(
            all_m[i].timestamp <= all_m[i + 1].timestamp
            for i in range(len(all_m) - 1)
        )

    # --- get_alert / list_alerts: filter by resource_id, severity, acknowledged ---
    def test_get_and_list_alerts(self) -> None:
        # get not found
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.get_alert("copalert-missing")
        assert exc_info.value.code == "NOT_FOUND"

        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        self.engine.set_threshold("res-2", "cpu", 50.0, 80.0)
        self.engine.record_metric("res-1", "cpu", 60.0)  # warning
        self.engine.record_metric("res-1", "cpu", 90.0)  # critical
        self.engine.record_metric("res-2", "cpu", 60.0)  # warning

        all_alerts = self.engine.list_alerts()
        assert len(all_alerts) == 3

        # get
        first = all_alerts[0]
        got = self.engine.get_alert(first.id)
        assert got.id == first.id

        # 按 resource_id 过滤
        res1 = self.engine.list_alerts(resource_id="res-1")
        assert len(res1) == 2
        # 按 severity 过滤
        crits = self.engine.list_alerts(severity="critical")
        assert len(crits) == 1
        warns = self.engine.list_alerts(severity="warning")
        assert len(warns) == 2
        # 按 acknowledged 过滤
        unacked = self.engine.list_alerts(acknowledged=False)
        assert len(unacked) == 3
        acked = self.engine.list_alerts(acknowledged=True)
        assert len(acked) == 0
        # 组合过滤
        combo = self.engine.list_alerts(resource_id="res-1", severity="critical")
        assert len(combo) == 1
        # 排序
        assert all(
            all_alerts[i].created_at <= all_alerts[i + 1].created_at
            for i in range(len(all_alerts) - 1)
        )

    # --- acknowledge_alert ---
    def test_acknowledge_alert(self) -> None:
        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        self.engine.record_metric("res-1", "cpu", 60.0)
        alert = self.engine.list_alerts()[0]
        assert alert.acknowledged is False

        acked = self.engine.acknowledge_alert(alert.id)
        assert acked.acknowledged is True
        assert acked.id == alert.id
        # 持久化
        assert self.engine.list_alerts(acknowledged=True)[0].id == alert.id
        assert self.engine.list_alerts(acknowledged=False) == []

        # acknowledge 不存在的 alert
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.acknowledge_alert("copalert-missing")
        assert exc_info.value.code == "NOT_FOUND"

    # --- get_dashboard: verify counts ---
    def test_get_dashboard(self) -> None:
        # 初始空态
        empty = self.engine.get_dashboard()
        assert empty == {
            "total_metrics": 0,
            "total_alerts": 0,
            "active_alerts": 0,
            "critical_alerts": 0,
            "warning_alerts": 0,
            "resources_monitored": 0,
        }

        self.engine.set_threshold("res-1", "cpu", 50.0, 80.0)
        self.engine.set_threshold("res-2", "cpu", 50.0, 80.0)
        self.engine.record_metric("res-1", "cpu", 30.0)   # normal
        self.engine.record_metric("res-1", "cpu", 60.0)   # warning → 1 alert
        self.engine.record_metric("res-2", "cpu", 90.0)   # critical → 1 alert

        dash = self.engine.get_dashboard()
        assert dash["total_metrics"] == 3
        assert dash["total_alerts"] == 2
        assert dash["active_alerts"] == 2  # 均未 ack
        assert dash["critical_alerts"] == 1
        assert dash["warning_alerts"] == 1
        assert dash["resources_monitored"] == 2  # res-1, res-2

        # acknowledge 一个后 active_alerts 减少
        alert_to_ack = self.engine.list_alerts(severity="critical")[0]
        self.engine.acknowledge_alert(alert_to_ack.id)
        dash2 = self.engine.get_dashboard()
        assert dash2["active_alerts"] == 1
        # total_alerts 不变
        assert dash2["total_alerts"] == 2

    # --- FIFO eviction for metrics ---
    def test_fifo_eviction_metrics(self) -> None:
        max_cap = CopRealtimeEngine._MAX_METRICS
        first = self.engine.record_metric(
            resource_id="res-first", metric_name="cpu", value=1.0
        )
        for i in range(max_cap):
            self.engine.record_metric(
                resource_id=f"res-{i}", metric_name="cpu", value=1.0
            )
        assert len(self.engine.list_metrics()) == max_cap
        with pytest.raises(AutoscaleTelemetryError) as exc_info:
            self.engine.get_metric(first.id)
        assert exc_info.value.code == "NOT_FOUND"


# ════════════════════ 单例 getter ════════════════════


def test_singleton_getters():
    assert get_predictive_autoscale_engine() is get_predictive_autoscale_engine()
    assert get_telemetry_format_engine() is get_telemetry_format_engine()
    assert get_volume_mount_engine() is get_volume_mount_engine()
    assert get_cop_realtime_engine() is get_cop_realtime_engine()
