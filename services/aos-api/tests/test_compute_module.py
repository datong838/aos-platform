"""W2-AP · Compute Module 组测试（#148 / #149 / #150）.

覆盖 ComputeSchedulerEngine / ComputeScalerEngine / ComputeResourceEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.compute_module import (
    # 模型
    ComputeModule,
    ComputeResourceEngine,
    ComputeResourceError,
    ComputeSchedulerEngine,
    ComputeSchedulerError,
    ComputeScalerEngine,
    ComputeScalerError,
    Replica,
    ResourceQuota,
    ScalePolicy,
    # getter
    get_compute_resource_engine,
    get_compute_scaler_engine,
    get_compute_scheduler_engine,
)


# ════════════════════ ComputeSchedulerEngine ════════════════════

class TestComputeScheduler:
    def setup_method(self) -> None:
        self.eng = ComputeSchedulerEngine()
        self.eng._modules = {}

    def test_register(self) -> None:
        module = self.eng.register(ComputeModule(name="n", image="img"))
        assert module.module_id.startswith("cm-")
        assert module.name == "n"
        assert module.image == "img"
        assert module.status == "pending"
        assert module.created_at is not None

    def test_get(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        fetched = self.eng.get(m.module_id)
        assert fetched.module_id == m.module_id
        assert fetched.name == "n"

    def test_list(self) -> None:
        self.eng.register(ComputeModule(name="n1", image="img"))
        self.eng.register(ComputeModule(name="n2", image="img"))
        items = self.eng.list()
        assert len(items) == 2

    def test_list_filter_status(self) -> None:
        m1 = self.eng.register(ComputeModule(name="n1", image="img"))
        self.eng.register(ComputeModule(name="n2", image="img"))
        self.eng.start(m1.module_id)
        running = self.eng.list(status="running")
        pending = self.eng.list(status="pending")
        assert len(running) == 1
        assert running[0].status == "running"
        assert len(pending) == 1
        assert pending[0].status == "pending"

    def test_start(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        started = self.eng.start(m.module_id)
        assert started.status == "running"
        assert started.container_id.startswith("ctr-")
        assert started.started_at is not None
        assert started.last_heartbeat_at is not None
        assert started.updated_at is not None

    def test_start_invalid_transition(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        self.eng.start(m.module_id)
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.start(m.module_id)
        assert exc.value.code == "INVALID_TRANSITION"

    def test_stop(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        self.eng.start(m.module_id)
        stopped = self.eng.stop(m.module_id)
        assert stopped.status == "stopped"
        assert stopped.updated_at is not None

    def test_stop_invalid_transition(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.stop(m.module_id)
        assert exc.value.code == "INVALID_TRANSITION"

    def test_restart(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        started = self.eng.start(m.module_id)
        old_ctr = started.container_id
        restarted = self.eng.restart(m.module_id)
        assert restarted.status == "running"
        assert restarted.container_id.startswith("ctr-")
        assert restarted.container_id != old_ctr
        assert restarted.updated_at is not None

    def test_restart_invalid_transition(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.restart(m.module_id)
        assert exc.value.code == "INVALID_TRANSITION"

    def test_heartbeat(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        started = self.eng.start(m.module_id)
        hb = self.eng.heartbeat(m.module_id)
        assert hb.last_heartbeat_at >= started.started_at
        assert hb.updated_at is not None

    def test_heartbeat_not_running(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.heartbeat(m.module_id)
        assert exc.value.code == "NOT_RUNNING"

    def test_fail(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        failed = self.eng.fail(m.module_id, "err")
        assert failed.status == "failed"
        assert failed.error_message == "err"
        assert failed.updated_at is not None

    def test_remove(self) -> None:
        m = self.eng.register(ComputeModule(name="n", image="img"))
        self.eng.remove(m.module_id)
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.get(m.module_id)
        assert exc.value.code == "NOT_FOUND"

    def test_missing_name(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.register(ComputeModule(name="", image="img"))
        assert exc.value.code == "MISSING_NAME"

    def test_missing_image(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.register(ComputeModule(name="n", image=""))
        assert exc.value.code == "MISSING_IMAGE"

    def test_not_found_get(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_start(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.start("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_stop(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.stop("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_restart(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.restart("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_heartbeat(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.heartbeat("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_fail(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.fail("nonexistent", "err")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_remove(self) -> None:
        with pytest.raises(ComputeSchedulerError) as exc:
            self.eng.remove("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_max_modules_eviction(self) -> None:
        from aos_api.compute_module import _MAX_COMPUTE_MODULES
        for i in range(_MAX_COMPUTE_MODULES + 5):
            self.eng.register(ComputeModule(name=f"n-{i}", image="img"))
        assert len(self.eng._modules) == _MAX_COMPUTE_MODULES


# ════════════════════ ComputeScalerEngine ════════════════════

class TestComputeScaler:
    def setup_method(self) -> None:
        self.eng = ComputeScalerEngine()
        self.eng._policies = {}
        self.eng._replicas = {}

    def test_register_policy(self) -> None:
        policy = self.eng.register_policy(ScalePolicy(module_id="m1"))
        assert policy.policy_id.startswith("sp-")
        assert policy.module_id == "m1"
        assert policy.status == "active"
        assert policy.created_at is not None

    def test_get_policy(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        fetched = self.eng.get_policy(p.policy_id)
        assert fetched.policy_id == p.policy_id
        assert fetched.module_id == "m1"

    def test_list_policies(self) -> None:
        self.eng.register_policy(ScalePolicy(module_id="m1"))
        self.eng.register_policy(ScalePolicy(module_id="m2"))
        items = self.eng.list_policies()
        assert len(items) == 2

    def test_list_policies_filter_module(self) -> None:
        self.eng.register_policy(ScalePolicy(module_id="m1"))
        self.eng.register_policy(ScalePolicy(module_id="m2"))
        items = self.eng.list_policies(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_update_policy(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        updated = self.eng.update_policy(p.policy_id, {"max_replicas": 20})
        assert updated.max_replicas == 20
        assert updated.updated_at is not None

    def test_update_policy_invalid_status(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.update_policy(p.policy_id, {"status": "bad"})
        assert exc.value.code == "INVALID_STATUS"

    def test_delete_policy(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        self.eng.delete_policy(p.policy_id)
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.get_policy(p.policy_id)
        assert exc.value.code == "NOT_FOUND"

    def test_evaluate_scale_up(self) -> None:
        p = self.eng.register_policy(
            ScalePolicy(module_id="m1", target_concurrency=100, scale_up_threshold=0.8)
        )
        result = self.eng.evaluate_scale(p.policy_id, 90)
        assert result["action"] == "scale_up"

    def test_evaluate_scale_down(self) -> None:
        p = self.eng.register_policy(
            ScalePolicy(
                module_id="m1", target_concurrency=100, scale_down_threshold=0.3
            )
        )
        result = self.eng.evaluate_scale(p.policy_id, 20)
        assert result["action"] == "scale_down"

    def test_evaluate_scale_none(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1", target_concurrency=100))
        result = self.eng.evaluate_scale(p.policy_id, 50)
        assert result["action"] == "none"

    def test_evaluate_scale_inactive(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1", target_concurrency=100))
        self.eng.update_policy(p.policy_id, {"status": "inactive"})
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.evaluate_scale(p.policy_id, 50)
        assert exc.value.code == "POLICY_INACTIVE"

    def test_scale_up(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        replicas = self.eng.scale_up(p.policy_id, count=2)
        assert len(replicas) == 2
        for r in replicas:
            assert r.replica_id.startswith("rep-")
            assert r.status == "pending"
            assert r.module_id == "m1"

    def test_scale_up_invalid_count(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.scale_up(p.policy_id, count=0)
        assert exc.value.code == "INVALID_COUNT"

    def test_scale_up_inactive(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        self.eng.update_policy(p.policy_id, {"status": "inactive"})
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.scale_up(p.policy_id, count=1)
        assert exc.value.code == "POLICY_INACTIVE"

    def test_scale_down(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        self.eng.scale_up(p.policy_id, count=3)
        down = self.eng.scale_down(p.policy_id, count=2)
        assert len(down) == 2
        for r in down:
            assert r.status == "unhealthy"

    def test_scale_down_invalid_count(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.scale_down(p.policy_id, count=0)
        assert exc.value.code == "INVALID_COUNT"

    def test_list_replicas(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        self.eng.scale_up(p.policy_id, count=2)
        items = self.eng.list_replicas(module_id="m1")
        assert len(items) == 2

    def test_list_replicas_filter_status(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        self.eng.scale_up(p.policy_id, count=2)
        items = self.eng.list_replicas(module_id="m1", status="pending")
        assert len(items) == 2
        for r in items:
            assert r.status == "pending"

    def test_mark_replica_unhealthy(self) -> None:
        p = self.eng.register_policy(ScalePolicy(module_id="m1"))
        replicas = self.eng.scale_up(p.policy_id, count=1)
        rid = replicas[0].replica_id
        marked = self.eng.mark_replica_unhealthy(rid)
        assert marked.status == "unhealthy"
        assert marked.updated_at is not None

    def test_missing_module_register(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.register_policy(ScalePolicy(module_id=""))
        assert exc.value.code == "MISSING_MODULE"

    def test_invalid_min_replicas(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.register_policy(ScalePolicy(module_id="m1", min_replicas=-1))
        assert exc.value.code == "INVALID_MIN_REPLICAS"

    def test_invalid_max_replicas(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.register_policy(
                ScalePolicy(module_id="m1", min_replicas=5, max_replicas=3)
            )
        assert exc.value.code == "INVALID_MAX_REPLICAS"

    def test_invalid_target_concurrency(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.register_policy(
                ScalePolicy(module_id="m1", target_concurrency=0)
            )
        assert exc.value.code == "INVALID_TARGET_CONCURRENCY"

    def test_invalid_threshold(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.register_policy(
                ScalePolicy(module_id="m1", scale_up_threshold=0)
            )
        assert exc.value.code == "INVALID_THRESHOLD"

    def test_invalid_threshold_up_le_down(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.register_policy(
                ScalePolicy(
                    module_id="m1", scale_up_threshold=0.3, scale_down_threshold=0.5
                )
            )
        assert exc.value.code == "INVALID_THRESHOLD"

    def test_not_found_get_policy(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.get_policy("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_evaluate(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.evaluate_scale("nonexistent", 10)
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_scale_up(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.scale_up("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_mark_replica(self) -> None:
        with pytest.raises(ComputeScalerError) as exc:
            self.eng.mark_replica_unhealthy("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_max_policies_eviction(self) -> None:
        from aos_api.compute_module import _MAX_SCALE_POLICIES
        for i in range(_MAX_SCALE_POLICIES + 5):
            self.eng.register_policy(ScalePolicy(module_id=f"m-{i}"))
        assert len(self.eng._policies) == _MAX_SCALE_POLICIES


# ════════════════════ ComputeResourceEngine ════════════════════

class TestComputeResource:
    def setup_method(self) -> None:
        self.eng = ComputeResourceEngine()
        self.eng._quotas = {}
        self.eng._module_index = {}

    def test_register(self) -> None:
        q = self.eng.register(ResourceQuota(module_id="m1"))
        assert q.quota_id.startswith("rq-")
        assert q.module_id == "m1"
        assert q.cpu_request == 0.5
        assert q.created_at is not None

    def test_register_overwrite(self) -> None:
        self.eng.register(ResourceQuota(module_id="m1", cpu_limit=1.0))
        self.eng.register(ResourceQuota(module_id="m1", cpu_limit=2.0))
        assert len(self.eng._quotas) == 1

    def test_get(self) -> None:
        q = self.eng.register(ResourceQuota(module_id="m1"))
        fetched = self.eng.get(q.quota_id)
        assert fetched.quota_id == q.quota_id
        assert fetched.module_id == "m1"

    def test_get_by_module(self) -> None:
        self.eng.register(ResourceQuota(module_id="m1"))
        q = self.eng.get_by_module("m1")
        assert q.module_id == "m1"

    def test_list(self) -> None:
        self.eng.register(ResourceQuota(module_id="m1"))
        self.eng.register(ResourceQuota(module_id="m2"))
        items = self.eng.list()
        assert len(items) == 2

    def test_list_filter_module(self) -> None:
        self.eng.register(ResourceQuota(module_id="m1"))
        self.eng.register(ResourceQuota(module_id="m2"))
        items = self.eng.list(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_update(self) -> None:
        q = self.eng.register(ResourceQuota(module_id="m1"))
        updated = self.eng.update(q.quota_id, {"cpu_limit": 2.0})
        assert updated.cpu_limit == 2.0
        assert updated.updated_at is not None

    def test_update_invalid_cpu_limit(self) -> None:
        q = self.eng.register(ResourceQuota(module_id="m1"))
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.update(q.quota_id, {"cpu_request": 3.0, "cpu_limit": 2.0})
        assert exc.value.code == "INVALID_CPU_LIMIT"

    def test_delete(self) -> None:
        q = self.eng.register(ResourceQuota(module_id="m1"))
        self.eng.delete(q.quota_id)
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.get(q.quota_id)
        assert exc.value.code == "NOT_FOUND"
        assert "m1" not in self.eng._module_index

    def test_validate_quota(self) -> None:
        self.eng.register(ResourceQuota(module_id="m1"))
        result = self.eng.validate_quota("m1")
        assert result["valid"] is True
        assert "quota" in result
        assert isinstance(result["quota"], dict)

    def test_compare_quota_fits(self) -> None:
        self.eng.register(
            ResourceQuota(
                module_id="m1", cpu_limit=1.0, memory_limit_mb=512
            )
        )
        result = self.eng.compare_quota("m1", 0.5, 256)
        assert result["fits"] is True

    def test_compare_quota_not_fit_cpu(self) -> None:
        self.eng.register(
            ResourceQuota(
                module_id="m1", cpu_limit=1.0, memory_limit_mb=512
            )
        )
        result = self.eng.compare_quota("m1", 2.0, 256)
        assert result["fits"] is False

    def test_compare_quota_not_fit_memory(self) -> None:
        self.eng.register(
            ResourceQuota(
                module_id="m1", cpu_limit=1.0, memory_limit_mb=512
            )
        )
        result = self.eng.compare_quota("m1", 0.5, 1024)
        assert result["fits"] is False

    def test_list_by_gpu(self) -> None:
        self.eng.register(ResourceQuota(module_id="m1", gpu_type="T4"))
        self.eng.register(ResourceQuota(module_id="m2", gpu_type=""))
        items = self.eng.list_by_gpu("T4")
        assert len(items) == 1
        assert items[0].gpu_type == "T4"

    def test_missing_module(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.register(ResourceQuota(module_id=""))
        assert exc.value.code == "MISSING_MODULE"

    def test_invalid_cpu_request(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.register(ResourceQuota(module_id="m1", cpu_request=-1))
        assert exc.value.code == "INVALID_CPU_REQUEST"

    def test_invalid_cpu_limit(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.register(
                ResourceQuota(module_id="m1", cpu_request=2.0, cpu_limit=1.0)
            )
        assert exc.value.code == "INVALID_CPU_LIMIT"

    def test_invalid_memory_limit(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.register(
                ResourceQuota(
                    module_id="m1", memory_request_mb=512, memory_limit_mb=256
                )
            )
        assert exc.value.code == "INVALID_MEMORY_LIMIT"

    def test_invalid_gpu_count(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.register(ResourceQuota(module_id="m1", gpu_count=-1))
        assert exc.value.code == "INVALID_GPU_COUNT"

    def test_invalid_gpu_type(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.register(ResourceQuota(module_id="m1", gpu_type="RTX"))
        assert exc.value.code == "INVALID_GPU_TYPE"

    def test_invalid_storage(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.register(
                ResourceQuota(module_id="m1", ephemeral_storage_gb=-1)
            )
        assert exc.value.code == "INVALID_STORAGE"

    def test_not_found_get(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_get_by_module(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.get_by_module("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.update("nonexistent", {})
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_delete(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.delete("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_validate(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.validate_quota("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_compare(self) -> None:
        with pytest.raises(ComputeResourceError) as exc:
            self.eng.compare_quota("nonexistent", 0.5, 256)
        assert exc.value.code == "NOT_FOUND"

    def test_max_quotas_eviction(self) -> None:
        from aos_api.compute_module import _MAX_RESOURCE_QUOTAS
        for i in range(_MAX_RESOURCE_QUOTAS + 5):
            self.eng.register(ResourceQuota(module_id=f"m-{i}"))
        assert len(self.eng._quotas) == _MAX_RESOURCE_QUOTAS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_compute_scheduler_singleton(self) -> None:
        a = get_compute_scheduler_engine()
        b = get_compute_scheduler_engine()
        assert a is b

    def test_compute_scaler_singleton(self) -> None:
        a = get_compute_scaler_engine()
        b = get_compute_scaler_engine()
        assert a is b

    def test_compute_resource_singleton(self) -> None:
        a = get_compute_resource_engine()
        b = get_compute_resource_engine()
        assert a is b
