"""W2-AP · Compute Module 引擎（#148 #149 #150）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_COMPUTE_MODULES = 200
_MAX_SCALE_POLICIES = 200
_MAX_REPLICAS = 200
_MAX_RESOURCE_QUOTAS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class ComputeSchedulerError(Exception):
    """Compute Module 调度错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ComputeScalerError(Exception):
    """Compute Module 副本扩缩错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ComputeResourceError(Exception):
    """Compute Module 资源约束错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #148 Compute Scheduler ════════════════════

class ComputeModule(BaseModel):
    module_id: str = ""
    name: str
    image: str
    command: str = ""
    args: list[str] = []
    env: dict = {}
    status: str = "pending"  # pending | scheduling | running | stopping | stopped | failed
    container_id: str = ""
    started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    error_message: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_MODULE_STATUSES = {"pending", "scheduling", "running", "stopping", "stopped", "failed"}


class ComputeSchedulerEngine:
    """Compute Module 调度引擎（容器模块生命周期）."""

    _instance: ComputeSchedulerEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._modules: dict[str, ComputeModule] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ComputeSchedulerEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, module: ComputeModule) -> ComputeModule:
        if not module.name or not module.name.strip():
            raise ComputeSchedulerError("MISSING_NAME", "name is required")
        if not module.image or not module.image.strip():
            raise ComputeSchedulerError("MISSING_IMAGE", "image is required")

        now = _utcnow()
        mid = f"cm-{uuid.uuid4().hex[:8]}"
        stored = module.model_copy(update={
            "module_id": mid,
            "status": "pending",
            "container_id": "",
            "started_at": None,
            "last_heartbeat_at": None,
            "error_message": "",
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._modules) >= _MAX_COMPUTE_MODULES:
                oldest = min(self._modules.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._modules[oldest.module_id]
            self._modules[mid] = stored
        return stored

    def get(self, module_id: str) -> ComputeModule:
        with self._lock:
            module = self._modules.get(module_id)
        if module is None:
            raise ComputeSchedulerError("NOT_FOUND", f"module {module_id} not found")
        return module

    def list(self, status: str | None = None) -> list[ComputeModule]:
        with self._lock:
            results = list(self._modules.values())
        if status:
            results = [m for m in results if m.status == status]
        return sorted(results, key=lambda m: m.created_at or datetime.min, reverse=True)

    def start(self, module_id: str) -> ComputeModule:
        with self._lock:
            module = self._modules.get(module_id)
            if module is None:
                raise ComputeSchedulerError("NOT_FOUND", f"module {module_id} not found")
            if module.status not in ("pending", "stopped", "failed"):
                raise ComputeSchedulerError(
                    "INVALID_TRANSITION",
                    f"cannot start from status {module.status}")
            now = _utcnow()
            # 模拟 scheduling -> running
            updated = module.model_copy(update={
                "status": "running",
                "container_id": f"ctr-{uuid.uuid4().hex[:8]}",
                "started_at": now,
                "last_heartbeat_at": now,
                "updated_at": now,
            })
            self._modules[module_id] = updated
        return updated

    def stop(self, module_id: str) -> ComputeModule:
        with self._lock:
            module = self._modules.get(module_id)
            if module is None:
                raise ComputeSchedulerError("NOT_FOUND", f"module {module_id} not found")
            if module.status != "running":
                raise ComputeSchedulerError(
                    "INVALID_TRANSITION",
                    f"cannot stop from status {module.status}")
            # 模拟 stopping -> stopped
            updated = module.model_copy(update={
                "status": "stopped",
                "updated_at": _utcnow(),
            })
            self._modules[module_id] = updated
        return updated

    def restart(self, module_id: str) -> ComputeModule:
        with self._lock:
            module = self._modules.get(module_id)
            if module is None:
                raise ComputeSchedulerError("NOT_FOUND", f"module {module_id} not found")
            if module.status != "running":
                raise ComputeSchedulerError(
                    "INVALID_TRANSITION",
                    f"cannot restart from status {module.status}")
            now = _utcnow()
            # 模拟 stopping -> scheduling -> running
            updated = module.model_copy(update={
                "status": "running",
                "container_id": f"ctr-{uuid.uuid4().hex[:8]}",
                "started_at": now,
                "last_heartbeat_at": now,
                "updated_at": now,
            })
            self._modules[module_id] = updated
        return updated

    def heartbeat(self, module_id: str) -> ComputeModule:
        with self._lock:
            module = self._modules.get(module_id)
            if module is None:
                raise ComputeSchedulerError("NOT_FOUND", f"module {module_id} not found")
            if module.status != "running":
                raise ComputeSchedulerError(
                    "NOT_RUNNING",
                    f"module {module_id} is not running (status={module.status})")
            now = _utcnow()
            updated = module.model_copy(update={
                "last_heartbeat_at": now,
                "updated_at": now,
            })
            self._modules[module_id] = updated
        return updated

    def fail(self, module_id: str, error_message: str) -> ComputeModule:
        with self._lock:
            module = self._modules.get(module_id)
            if module is None:
                raise ComputeSchedulerError("NOT_FOUND", f"module {module_id} not found")
            updated = module.model_copy(update={
                "status": "failed",
                "error_message": error_message,
                "updated_at": _utcnow(),
            })
            self._modules[module_id] = updated
        return updated

    def remove(self, module_id: str) -> None:
        with self._lock:
            if module_id not in self._modules:
                raise ComputeSchedulerError("NOT_FOUND", f"module {module_id} not found")
            del self._modules[module_id]


_compute_scheduler_engine: ComputeSchedulerEngine | None = None
_compute_scheduler_engine_lock = threading.Lock()


def get_compute_scheduler_engine() -> ComputeSchedulerEngine:
    global _compute_scheduler_engine
    if _compute_scheduler_engine is None:
        with _compute_scheduler_engine_lock:
            if _compute_scheduler_engine is None:
                _compute_scheduler_engine = ComputeSchedulerEngine.get_instance()
    return _compute_scheduler_engine


# ════════════════════ #149 Compute Scaler ════════════════════

class ScalePolicy(BaseModel):
    policy_id: str = ""
    module_id: str
    min_replicas: int = 1
    max_replicas: int = 10
    target_concurrency: int = 100
    scale_up_threshold: float = 0.8   # 当前并发/目标 >= 阈值 → 扩容
    scale_down_threshold: float = 0.3  # 当前并发/目标 <= 阈值 → 缩容
    status: str = "active"  # active | inactive
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Replica(BaseModel):
    replica_id: str = ""
    module_id: str
    status: str = "pending"  # pending | running | unhealthy
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_POLICY_STATUSES = {"active", "inactive"}
_VALID_REPLICA_STATUSES = {"pending", "running", "unhealthy"}


class ComputeScalerEngine:
    """Compute Module 副本扩缩引擎."""

    _instance: ComputeScalerEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._policies: dict[str, ScalePolicy] = {}
        self._replicas: dict[str, Replica] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ComputeScalerEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_policy(self, policy: ScalePolicy) -> ScalePolicy:
        if not policy.module_id or not policy.module_id.strip():
            raise ComputeScalerError("MISSING_MODULE", "module_id is required")
        if policy.min_replicas < 0:
            raise ComputeScalerError("INVALID_MIN_REPLICAS", "min_replicas must be >= 0")
        if policy.max_replicas < policy.min_replicas:
            raise ComputeScalerError(
                "INVALID_MAX_REPLICAS", "max_replicas must be >= min_replicas")
        if policy.target_concurrency <= 0:
            raise ComputeScalerError(
                "INVALID_TARGET_CONCURRENCY", "target_concurrency must be > 0")
        if not (0 < policy.scale_up_threshold <= 1):
            raise ComputeScalerError(
                "INVALID_THRESHOLD", "scale_up_threshold must be in (0, 1]")
        if not (0 <= policy.scale_down_threshold < 1):
            raise ComputeScalerError(
                "INVALID_THRESHOLD", "scale_down_threshold must be in [0, 1)")
        if policy.scale_up_threshold <= policy.scale_down_threshold:
            raise ComputeScalerError(
                "INVALID_THRESHOLD",
                "scale_up_threshold must be > scale_down_threshold")

        now = _utcnow()
        pid = f"sp-{uuid.uuid4().hex[:8]}"
        stored = policy.model_copy(update={
            "policy_id": pid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._policies) >= _MAX_SCALE_POLICIES:
                oldest = min(self._policies.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._policies[oldest.policy_id]
            self._policies[pid] = stored
        return stored

    def get_policy(self, policy_id: str) -> ScalePolicy:
        with self._lock:
            policy = self._policies.get(policy_id)
        if policy is None:
            raise ComputeScalerError("NOT_FOUND", f"policy {policy_id} not found")
        return policy

    def list_policies(self, module_id: str | None = None,
                      status: str | None = None) -> list[ScalePolicy]:
        with self._lock:
            results = list(self._policies.values())
        if module_id:
            results = [p for p in results if p.module_id == module_id]
        if status:
            results = [p for p in results if p.status == status]
        return sorted(results, key=lambda p: p.created_at or datetime.min, reverse=True)

    def update_policy(self, policy_id: str, updates: dict) -> ScalePolicy:
        if "status" in updates and updates["status"] not in _VALID_POLICY_STATUSES:
            raise ComputeScalerError(
                "INVALID_STATUS", f"status must be one of {_VALID_POLICY_STATUSES}")
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy is None:
                raise ComputeScalerError("NOT_FOUND", f"policy {policy_id} not found")
            data = policy.model_dump()
            data.update(updates)
            if "min_replicas" in updates or "max_replicas" in updates:
                min_r = data.get("min_replicas", policy.min_replicas)
                max_r = data.get("max_replicas", policy.max_replicas)
                if min_r < 0:
                    raise ComputeScalerError(
                        "INVALID_MIN_REPLICAS", "min_replicas must be >= 0")
                if max_r < min_r:
                    raise ComputeScalerError(
                        "INVALID_MAX_REPLICAS", "max_replicas must be >= min_replicas")
            if "scale_up_threshold" in updates or "scale_down_threshold" in updates:
                up = data.get("scale_up_threshold", policy.scale_up_threshold)
                down = data.get("scale_down_threshold", policy.scale_down_threshold)
                if not (0 < up <= 1):
                    raise ComputeScalerError(
                        "INVALID_THRESHOLD", "scale_up_threshold must be in (0, 1]")
                if not (0 <= down < 1):
                    raise ComputeScalerError(
                        "INVALID_THRESHOLD", "scale_down_threshold must be in [0, 1)")
                if up <= down:
                    raise ComputeScalerError(
                        "INVALID_THRESHOLD",
                        "scale_up_threshold must be > scale_down_threshold")
            data["updated_at"] = _utcnow()
            updated = ScalePolicy(**data)
            self._policies[policy_id] = updated
        return updated

    def delete_policy(self, policy_id: str) -> None:
        with self._lock:
            if policy_id not in self._policies:
                raise ComputeScalerError("NOT_FOUND", f"policy {policy_id} not found")
            del self._policies[policy_id]

    def evaluate_scale(self, policy_id: str, current_concurrency: int) -> dict:
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy is None:
                raise ComputeScalerError("NOT_FOUND", f"policy {policy_id} not found")
            if policy.status != "active":
                raise ComputeScalerError(
                    "POLICY_INACTIVE", f"policy {policy_id} is not active")
            target = policy.target_concurrency
            ratio = current_concurrency / target if target else 0.0
            if ratio >= policy.scale_up_threshold:
                action = "scale_up"
            elif ratio <= policy.scale_down_threshold:
                action = "scale_down"
            else:
                action = "none"
        return {
            "action": action,
            "ratio": ratio,
            "current": current_concurrency,
            "target": target,
        }

    def scale_up(self, policy_id: str, count: int = 1) -> list[Replica]:
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy is None:
                raise ComputeScalerError("NOT_FOUND", f"policy {policy_id} not found")
            if count <= 0:
                raise ComputeScalerError("INVALID_COUNT", "count must be > 0")
            if policy.status != "active":
                raise ComputeScalerError(
                    "POLICY_INACTIVE", f"policy {policy_id} is not active")
            now = _utcnow()
            created: list[Replica] = []
            for _ in range(count):
                rid = f"rep-{uuid.uuid4().hex[:8]}"
                replica = Replica(
                    replica_id=rid,
                    module_id=policy.module_id,
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
                if len(self._replicas) >= _MAX_REPLICAS:
                    oldest = min(self._replicas.values(),
                                 key=lambda x: x.created_at or datetime.min)
                    del self._replicas[oldest.replica_id]
                self._replicas[rid] = replica
                created.append(replica)
        return created

    def scale_down(self, policy_id: str, count: int = 1) -> list[Replica]:
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy is None:
                raise ComputeScalerError("NOT_FOUND", f"policy {policy_id} not found")
            if count <= 0:
                raise ComputeScalerError("INVALID_COUNT", "count must be > 0")
            if policy.status != "active":
                raise ComputeScalerError(
                    "POLICY_INACTIVE", f"policy {policy_id} is not active")
            candidates = [r for r in self._replicas.values()
                          if r.module_id == policy.module_id
                          and r.status in ("pending", "running")]
            candidates = sorted(candidates,
                                key=lambda x: x.created_at or datetime.min)
            now = _utcnow()
            downed: list[Replica] = []
            for replica in candidates[:count]:
                updated = replica.model_copy(update={
                    "status": "unhealthy",
                    "updated_at": now,
                })
                self._replicas[replica.replica_id] = updated
                downed.append(updated)
        return downed

    def list_replicas(self, module_id: str,
                      status: str | None = None) -> list[Replica]:
        with self._lock:
            results = [r for r in self._replicas.values() if r.module_id == module_id]
        if status:
            results = [r for r in results if r.status == status]
        return sorted(results, key=lambda r: r.created_at or datetime.min, reverse=True)

    def mark_replica_unhealthy(self, replica_id: str) -> Replica:
        with self._lock:
            replica = self._replicas.get(replica_id)
            if replica is None:
                raise ComputeScalerError("NOT_FOUND", f"replica {replica_id} not found")
            updated = replica.model_copy(update={
                "status": "unhealthy",
                "updated_at": _utcnow(),
            })
            self._replicas[replica_id] = updated
        return updated


_compute_scaler_engine: ComputeScalerEngine | None = None
_compute_scaler_engine_lock = threading.Lock()


def get_compute_scaler_engine() -> ComputeScalerEngine:
    global _compute_scaler_engine
    if _compute_scaler_engine is None:
        with _compute_scaler_engine_lock:
            if _compute_scaler_engine is None:
                _compute_scaler_engine = ComputeScalerEngine.get_instance()
    return _compute_scaler_engine


# ════════════════════ #150 Compute Resource ════════════════════

class ResourceQuota(BaseModel):
    quota_id: str = ""
    module_id: str
    cpu_request: float = 0.5      # CPU 核数
    cpu_limit: float = 1.0
    memory_request_mb: int = 256   # MB
    memory_limit_mb: int = 512
    gpu_count: int = 0
    gpu_type: str = ""             # 如 "T4", "A100"
    ephemeral_storage_gb: float = 1.0
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_GPU_TYPES = {"", "T4", "A100", "V100", "H100"}


class ComputeResourceEngine:
    """Compute Module 资源约束引擎."""

    _instance: ComputeResourceEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._quotas: dict[str, ResourceQuota] = {}
        self._module_index: dict[str, str] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ComputeResourceEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, quota: ResourceQuota) -> ResourceQuota:
        if not quota.module_id or not quota.module_id.strip():
            raise ComputeResourceError("MISSING_MODULE", "module_id is required")
        if quota.cpu_request < 0:
            raise ComputeResourceError("INVALID_CPU_REQUEST", "cpu_request must be >= 0")
        if quota.cpu_limit < quota.cpu_request:
            raise ComputeResourceError(
                "INVALID_CPU_LIMIT", "cpu_limit must be >= cpu_request")
        if quota.memory_request_mb < 0:
            raise ComputeResourceError(
                "INVALID_MEMORY_REQUEST", "memory_request_mb must be >= 0")
        if quota.memory_limit_mb < quota.memory_request_mb:
            raise ComputeResourceError(
                "INVALID_MEMORY_LIMIT", "memory_limit_mb must be >= memory_request_mb")
        if quota.gpu_count < 0:
            raise ComputeResourceError("INVALID_GPU_COUNT", "gpu_count must be >= 0")
        if quota.gpu_type not in _VALID_GPU_TYPES:
            raise ComputeResourceError(
                "INVALID_GPU_TYPE", f"gpu_type must be one of {_VALID_GPU_TYPES}")
        if quota.ephemeral_storage_gb < 0:
            raise ComputeResourceError(
                "INVALID_STORAGE", "ephemeral_storage_gb must be >= 0")

        now = _utcnow()
        qid = f"rq-{uuid.uuid4().hex[:8]}"
        stored = quota.model_copy(update={
            "quota_id": qid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            # 同一 module_id 已有 quota → 覆盖更新（不新增）
            existing_qid = self._module_index.get(quota.module_id)
            if existing_qid:
                self._quotas.pop(existing_qid, None)
            if len(self._quotas) >= _MAX_RESOURCE_QUOTAS:
                oldest = min(self._quotas.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._quotas[oldest.quota_id]
                self._module_index.pop(oldest.module_id, None)
            self._quotas[qid] = stored
            self._module_index[quota.module_id] = qid
        return stored

    def get(self, quota_id: str) -> ResourceQuota:
        with self._lock:
            quota = self._quotas.get(quota_id)
        if quota is None:
            raise ComputeResourceError("NOT_FOUND", f"quota {quota_id} not found")
        return quota

    def get_by_module(self, module_id: str) -> ResourceQuota:
        if not module_id or not module_id.strip():
            raise ComputeResourceError("MISSING_MODULE", "module_id is required")
        with self._lock:
            qid = self._module_index.get(module_id)
            quota = self._quotas.get(qid) if qid else None
        if quota is None:
            raise ComputeResourceError(
                "NOT_FOUND", f"quota for module {module_id} not found")
        return quota

    def list(self, module_id: str | None = None) -> list[ResourceQuota]:
        with self._lock:
            results = list(self._quotas.values())
        if module_id:
            results = [q for q in results if q.module_id == module_id]
        return sorted(results, key=lambda q: q.created_at or datetime.min, reverse=True)

    def update(self, quota_id: str, updates: dict) -> ResourceQuota:
        with self._lock:
            quota = self._quotas.get(quota_id)
            if quota is None:
                raise ComputeResourceError("NOT_FOUND", f"quota {quota_id} not found")
            data = quota.model_dump()
            data.update(updates)
            if "cpu_request" in updates or "cpu_limit" in updates:
                cpu_req = data.get("cpu_request", quota.cpu_request)
                cpu_lim = data.get("cpu_limit", quota.cpu_limit)
                if cpu_req < 0:
                    raise ComputeResourceError(
                        "INVALID_CPU_REQUEST", "cpu_request must be >= 0")
                if cpu_lim < cpu_req:
                    raise ComputeResourceError(
                        "INVALID_CPU_LIMIT", "cpu_limit must be >= cpu_request")
            if "memory_request_mb" in updates or "memory_limit_mb" in updates:
                mem_req = data.get("memory_request_mb", quota.memory_request_mb)
                mem_lim = data.get("memory_limit_mb", quota.memory_limit_mb)
                if mem_req < 0:
                    raise ComputeResourceError(
                        "INVALID_MEMORY_REQUEST", "memory_request_mb must be >= 0")
                if mem_lim < mem_req:
                    raise ComputeResourceError(
                        "INVALID_MEMORY_LIMIT", "memory_limit_mb must be >= memory_request_mb")
            if "gpu_type" in updates and data.get("gpu_type") not in _VALID_GPU_TYPES:
                raise ComputeResourceError(
                    "INVALID_GPU_TYPE", f"gpu_type must be one of {_VALID_GPU_TYPES}")
            if "ephemeral_storage_gb" in updates and data.get("ephemeral_storage_gb", 0) < 0:
                raise ComputeResourceError(
                    "INVALID_STORAGE", "ephemeral_storage_gb must be >= 0")
            data["updated_at"] = _utcnow()
            updated = ResourceQuota(**data)
            self._quotas[quota_id] = updated
        return updated

    def delete(self, quota_id: str) -> None:
        with self._lock:
            quota = self._quotas.get(quota_id)
            if quota is None:
                raise ComputeResourceError("NOT_FOUND", f"quota {quota_id} not found")
            self._module_index.pop(quota.module_id, None)
            del self._quotas[quota_id]

    def validate_quota(self, module_id: str) -> dict:
        quota = self.get_by_module(module_id)
        return {"valid": True, "quota": quota.model_dump()}

    def compare_quota(self, module_id: str, requested_cpu: float,
                      requested_memory_mb: int) -> dict:
        quota = self.get_by_module(module_id)
        fits = (requested_cpu <= quota.cpu_limit
                and requested_memory_mb <= quota.memory_limit_mb)
        if fits:
            reason = "requested resources fit within quota limits"
        else:
            reason = "requested resources exceed quota limits"
        return {"fits": fits, "reason": reason, "quota": quota.model_dump()}

    def list_by_gpu(self, gpu_type: str) -> list[ResourceQuota]:
        with self._lock:
            results = [q for q in self._quotas.values() if q.gpu_type == gpu_type]
        return sorted(results, key=lambda q: q.created_at or datetime.min, reverse=True)


_compute_resource_engine: ComputeResourceEngine | None = None
_compute_resource_engine_lock = threading.Lock()


def get_compute_resource_engine() -> ComputeResourceEngine:
    global _compute_resource_engine
    if _compute_resource_engine is None:
        with _compute_resource_engine_lock:
            if _compute_resource_engine is None:
                _compute_resource_engine = ComputeResourceEngine.get_instance()
    return _compute_resource_engine
