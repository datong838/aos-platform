"""W1-4 · Build 引擎。

Job/JobSpec 模型 + 生命周期状态机 + 事务锁定 + 结构化日志收集。
内存存储，同步执行器（真异步线程池属后续项）。

详见 docs/palantier/20_tech/220tech_build-engine.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

from aos_api.jobs.retry import DeadLetterQueue, RetryPolicy


# --------------------------------------------------------------------------- #
# 数据模型
# --------------------------------------------------------------------------- #
class JobStep(BaseModel):
    name: str
    type: str = "transform"
    config: dict[str, Any] = Field(default_factory=dict)


class JobSpec(BaseModel):
    inputs: list[str]
    steps: list[JobStep] = Field(default_factory=list)
    outputs: list[str]
    name: str = "untitled-build"


class LogEntry(BaseModel):
    timestamp: str
    level: str  # INFO | WARN | ERROR
    message: str


class Job(BaseModel):
    id: str
    spec: JobSpec
    status: str = "PENDING"
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    logs: list[LogEntry] = Field(default_factory=list)
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3


# --------------------------------------------------------------------------- #
# 错误
# --------------------------------------------------------------------------- #
class JobError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# --------------------------------------------------------------------------- #
# 引擎
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BuildEngine:
    def __init__(self, sleeper: Callable[[float], None] | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self._locks: dict[str, str] = {}  # dataset_rid → job_id
        self._mutex = threading.Lock()
        self._sleeper = sleeper or time.sleep
        self._dlq = DeadLetterQueue()

    # ---- 创建 + 执行 ----
    def create_job(self, spec: JobSpec) -> Job:
        self._validate_spec(spec)
        job = Job(id=str(uuid.uuid4()), spec=spec, created_at=_now())
        with self._mutex:
            self._jobs[job.id] = job
        self._execute(job)
        return job

    def _validate_spec(self, spec: JobSpec) -> None:
        if not spec.inputs:
            raise JobError("INVALID_SPEC", "JobSpec inputs 不可为空")
        if not spec.outputs:
            raise JobError("INVALID_SPEC", "JobSpec outputs 不可为空")

    def _execute(self, job: Job) -> None:
        policy = RetryPolicy(max_retries=job.max_retries)
        for attempt in range(job.max_retries + 1):
            locked: list[str] = []
            try:
                for ds in job.spec.outputs:
                    if not self._acquire_lock(ds, job.id):
                        raise JobError(
                            "DATASET_LOCKED",
                            f"数据集 {ds} 正被其他 Build 锁定",
                        )
                    locked.append(ds)

                if not job.started_at:
                    job.started_at = _now()
                job.status = "RUNNING"
                if attempt == 0:
                    self._log(job, "INFO", f"Build 启动：{job.spec.name}")
                else:
                    self._log(job, "INFO", f"Build 第 {attempt} 次重试")

                for step in job.spec.steps:
                    if job.status == "CANCELLED":
                        self._log(job, "WARN", f"步骤 {step.name} 被取消跳过")
                        return
                    fail_n = step.config.get("_fail_n", 0)
                    if fail_n > 0:
                        step.config["_fail_n"] = fail_n - 1
                        raise JobError(
                            "STEP_FAILED",
                            f"步骤 {step.name} 执行失败（模拟）",
                        )
                    self._log(job, "INFO", f"执行步骤：{step.name}（{step.type}）")

                job.status = "SUCCEEDED"
                job.finished_at = _now()
                self._log(job, "INFO", "Build 成功完成")
                return

            except JobError as exc:
                if policy.should_retry(attempt):
                    job.retry_count = attempt + 1
                    backoff = policy.compute_backoff(attempt)
                    self._log(
                        job, "WARN",
                        f"第 {attempt + 1} 次失败：{exc.message}，{backoff}s 后重试",
                    )
                    self._sleeper(backoff)
                else:
                    job.retry_count = attempt
                    job.status = "FAILED"
                    job.error = exc.message
                    job.finished_at = _now()
                    self._log(
                        job, "ERROR",
                        f"超过最大重试次数 {job.max_retries}，进入死信队列：{exc.message}",
                    )
                    self._dlq.push(job)
                    return
            finally:
                for ds in locked:
                    self._release_lock(ds)

    # ---- 查询 ----
    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    # ---- 取消 ----
    def cancel_job(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobError("NOT_FOUND", f"Job {job_id} 不存在")
        if job.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            raise JobError("ALREADY_FINISHED", f"Job 已终态：{job.status}")
        job.status = "CANCELLED"
        job.finished_at = _now()
        self._log(job, "WARN", "Job 被手动取消")
        return job

    # ---- 重试 ----
    def retry_job(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobError("NOT_FOUND", f"Job {job_id} 不存在")
        return self.create_job(job.spec)

    # ---- 死信队列 ----
    @property
    def dlq(self) -> DeadLetterQueue:
        return self._dlq

    # ---- 锁管理 ----
    def _acquire_lock(self, dataset_rid: str, job_id: str) -> bool:
        with self._mutex:
            holder = self._locks.get(dataset_rid)
            if holder is not None:
                return False
            self._locks[dataset_rid] = job_id
            return True

    def _release_lock(self, dataset_rid: str) -> None:
        with self._mutex:
            self._locks.pop(dataset_rid, None)

    def is_locked(self, dataset_rid: str) -> bool:
        with self._mutex:
            return dataset_rid in self._locks

    # ---- 日志 ----
    def _log(self, job: Job, level: str, message: str) -> None:
        job.logs.append(LogEntry(timestamp=_now(), level=level, message=message))


# 全局单例
_engine = BuildEngine()


def get_engine() -> BuildEngine:
    return _engine
