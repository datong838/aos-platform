"""W2-AZ · Pipeline Builder Extra 引擎（#18 #19 #20）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel

_MAX_BRANCHES = 200
_MAX_CONFIGS = 200
_MAX_EXPECTATIONS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


# ════════════════════ Error Classes ════════════════════

class PipelineBuilderExtraError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PipelineBranchError(PipelineBuilderExtraError):
    pass


class PipelineManagementError(PipelineBuilderExtraError):
    pass


class PipelineDataExpectationError(PipelineBuilderExtraError):
    pass


# ════════════════════ #18 Pipeline Branch Engine ════════════════════

class BranchStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    MERGED = "merged"
    REVERTED = "reverted"


class PipelineBranch(BaseModel):
    branch_id: str = ""
    pipeline_id: str
    name: str
    base_branch_id: Optional[str] = None
    status: str = BranchStatus.DRAFT.value
    protection_enabled: bool = False
    protection_rules: Optional[dict] = None
    created_by: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


_VALID_BRANCH_STATUS = {e.value for e in BranchStatus}


class PipelineBranchEngine:
    """Pipeline Builder 分支版本引擎."""

    _instance: Optional[PipelineBranchEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._branches: dict[str, PipelineBranch] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> PipelineBranchEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_branch(
        self,
        pipeline_id: str,
        name: str,
        base_branch_id: Optional[str] = None,
        protection_enabled: bool = False,
        created_by: str = "",
    ) -> PipelineBranch:
        if not pipeline_id or not pipeline_id.strip():
            raise PipelineBranchError("MISSING_PIPELINE", "pipeline_id is required")
        if not name or not name.strip():
            raise PipelineBranchError("MISSING_NAME", "name is required")

        now = _utcnow()
        bid = f"pb-{uuid.uuid4().hex[:8]}"
        branch = PipelineBranch(
            branch_id=bid,
            pipeline_id=pipeline_id,
            name=name,
            base_branch_id=base_branch_id,
            status=BranchStatus.DRAFT.value,
            protection_enabled=protection_enabled,
            protection_rules=None,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            if len(self._branches) >= _MAX_BRANCHES:
                oldest = min(
                    self._branches.values(),
                    key=lambda x: x.updated_at or datetime.min,
                )
                del self._branches[oldest.branch_id]
            self._branches[bid] = branch

        return branch

    def get_branch(self, branch_id: str) -> PipelineBranch:
        with self._lock:
            branch = self._branches.get(branch_id)
        if branch is None:
            raise PipelineBranchError("NOT_FOUND", f"branch {branch_id} not found")
        return branch

    def list_branches(
        self,
        pipeline_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[PipelineBranch]:
        with self._lock:
            results = list(self._branches.values())
        if pipeline_id:
            results = [b for b in results if b.pipeline_id == pipeline_id]
        if status:
            results = [b for b in results if b.status == status]
        return sorted(
            results,
            key=lambda b: b.updated_at or datetime.min,
            reverse=True,
        )

    def update_branch(
        self,
        branch_id: str,
        name: Optional[str] = None,
        protection_enabled: Optional[bool] = None,
        protection_rules: Optional[dict] = None,
    ) -> PipelineBranch:
        with self._lock:
            branch = self._branches.get(branch_id)
            if branch is None:
                raise PipelineBranchError("NOT_FOUND", f"branch {branch_id} not found")

            data = branch.model_dump()
            if name is not None:
                data["name"] = name
            if protection_enabled is not None:
                data["protection_enabled"] = protection_enabled
            if protection_rules is not None:
                data["protection_rules"] = protection_rules
            data["updated_at"] = _utcnow()

            updated = PipelineBranch(**data)
            self._branches[branch_id] = updated

        return updated

    def delete_branch(self, branch_id: str) -> bool:
        with self._lock:
            if branch_id not in self._branches:
                return False
            del self._branches[branch_id]
        return True

    def approve_branch(self, branch_id: str) -> PipelineBranch:
        with self._lock:
            branch = self._branches.get(branch_id)
            if branch is None:
                raise PipelineBranchError("NOT_FOUND", f"branch {branch_id} not found")

            if branch.status not in (BranchStatus.DRAFT.value, BranchStatus.REVIEW.value):
                raise PipelineBranchError(
                    "INVALID_STATUS",
                    f"cannot approve branch with status {branch.status}",
                )

            data = branch.model_dump()
            data["status"] = BranchStatus.APPROVED.value
            data["updated_at"] = _utcnow()

            updated = PipelineBranch(**data)
            self._branches[branch_id] = updated

        return updated

    def merge_branch(self, branch_id: str, target_branch_id: str) -> PipelineBranch:
        with self._lock:
            branch = self._branches.get(branch_id)
            if branch is None:
                raise PipelineBranchError("NOT_FOUND", f"branch {branch_id} not found")

            if branch.status != BranchStatus.APPROVED.value:
                raise PipelineBranchError(
                    "INVALID_STATUS",
                    f"cannot merge branch with status {branch.status}",
                )

            target = self._branches.get(target_branch_id)
            if target is None:
                raise PipelineBranchError("NOT_FOUND", f"target branch {target_branch_id} not found")

            data = branch.model_dump()
            data["status"] = BranchStatus.MERGED.value
            data["updated_at"] = _utcnow()

            updated = PipelineBranch(**data)
            self._branches[branch_id] = updated

        return updated

    def revert_branch(self, branch_id: str) -> PipelineBranch:
        with self._lock:
            branch = self._branches.get(branch_id)
            if branch is None:
                raise PipelineBranchError("NOT_FOUND", f"branch {branch_id} not found")

            if branch.status != BranchStatus.MERGED.value:
                raise PipelineBranchError(
                    "INVALID_STATUS",
                    f"cannot revert branch with status {branch.status}",
                )

            data = branch.model_dump()
            data["status"] = BranchStatus.REVERTED.value
            data["updated_at"] = _utcnow()

            updated = PipelineBranch(**data)
            self._branches[branch_id] = updated

        return updated


_branch_engine: Optional[PipelineBranchEngine] = None
_branch_engine_lock = threading.Lock()


def get_branch_engine() -> PipelineBranchEngine:
    global _branch_engine
    if _branch_engine is None:
        with _branch_engine_lock:
            if _branch_engine is None:
                _branch_engine = PipelineBranchEngine.get_instance()
    return _branch_engine


# ════════════════════ #19 Pipeline Management Engine ════════════════════

class PipelineConfig(BaseModel):
    config_id: str = ""
    pipeline_id: str
    checkpoints: Optional[dict] = None
    color_groups: Optional[dict] = None
    custom_functions: Optional[dict] = None
    folders: Optional[dict] = None
    sampling_config: Optional[dict] = None
    task_groups: Optional[dict] = None
    parameters: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PipelineManagementEngine:
    """Pipeline Builder 管道管理引擎."""

    _instance: Optional[PipelineManagementEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._configs: dict[str, PipelineConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> PipelineManagementEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_config(
        self,
        pipeline_id: str,
        checkpoints: Optional[dict] = None,
        color_groups: Optional[dict] = None,
        custom_functions: Optional[dict] = None,
        folders: Optional[dict] = None,
        sampling_config: Optional[dict] = None,
        task_groups: Optional[dict] = None,
        parameters: Optional[dict] = None,
    ) -> PipelineConfig:
        if not pipeline_id or not pipeline_id.strip():
            raise PipelineManagementError("MISSING_PIPELINE", "pipeline_id is required")

        now = _utcnow()
        cid = f"pc-{uuid.uuid4().hex[:8]}"
        config = PipelineConfig(
            config_id=cid,
            pipeline_id=pipeline_id,
            checkpoints=checkpoints,
            color_groups=color_groups,
            custom_functions=custom_functions,
            folders=folders,
            sampling_config=sampling_config,
            task_groups=task_groups,
            parameters=parameters,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            if len(self._configs) >= _MAX_CONFIGS:
                oldest = min(
                    self._configs.values(),
                    key=lambda x: x.updated_at or datetime.min,
                )
                del self._configs[oldest.config_id]
            self._configs[cid] = config

        return config

    def get_config(self, config_id: str) -> PipelineConfig:
        with self._lock:
            config = self._configs.get(config_id)
        if config is None:
            raise PipelineManagementError("NOT_FOUND", f"config {config_id} not found")
        return config

    def get_config_by_pipeline(self, pipeline_id: str) -> PipelineConfig:
        with self._lock:
            results = [c for c in self._configs.values() if c.pipeline_id == pipeline_id]
        if not results:
            raise PipelineManagementError(
                "NOT_FOUND",
                f"no config found for pipeline {pipeline_id}",
            )
        return sorted(
            results,
            key=lambda c: c.updated_at or datetime.min,
            reverse=True,
        )[0]

    def list_configs(self, pipeline_id: Optional[str] = None) -> List[PipelineConfig]:
        with self._lock:
            results = list(self._configs.values())
        if pipeline_id:
            results = [c for c in results if c.pipeline_id == pipeline_id]
        return sorted(
            results,
            key=lambda c: c.updated_at or datetime.min,
            reverse=True,
        )

    def update_config(self, config_id: str, **kwargs: Any) -> PipelineConfig:
        with self._lock:
            config = self._configs.get(config_id)
            if config is None:
                raise PipelineManagementError("NOT_FOUND", f"config {config_id} not found")

            data = config.model_dump()
            data.update(kwargs)
            data["updated_at"] = _utcnow()

            updated = PipelineConfig(**data)
            self._configs[config_id] = updated

        return updated

    def delete_config(self, config_id: str) -> bool:
        with self._lock:
            if config_id not in self._configs:
                return False
            del self._configs[config_id]
        return True


_management_engine: Optional[PipelineManagementEngine] = None
_management_engine_lock = threading.Lock()


def get_management_engine() -> PipelineManagementEngine:
    global _management_engine
    if _management_engine is None:
        with _management_engine_lock:
            if _management_engine is None:
                _management_engine = PipelineManagementEngine.get_instance()
    return _management_engine


# ════════════════════ #20 Pipeline Data Expectation Engine ════════════════════

class ExpectationType(str, Enum):
    PRIMARY_KEY = "primary_key"
    ROW_COUNT = "row_count"
    COLUMN_DISTINCT = "column_distinct"
    COLUMN_NULLS = "column_nulls"
    CUSTOM_SQL = "custom_sql"


class ExpectationSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


_VALID_EXPECTATION_TYPES = {e.value for e in ExpectationType}
_VALID_SEVERITIES = {e.value for e in ExpectationSeverity}


class DataExpectation(BaseModel):
    expectation_id: str = ""
    pipeline_id: str
    name: str
    expectation_type: str
    config: Optional[dict] = None
    severity: str = ExpectationSeverity.WARNING.value
    enabled: bool = True
    last_checked_at: Optional[datetime] = None
    last_result: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PipelineDataExpectationEngine:
    """Pipeline Builder 数据期望引擎."""

    _instance: Optional[PipelineDataExpectationEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._expectations: dict[str, DataExpectation] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> PipelineDataExpectationEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_expectation(
        self,
        pipeline_id: str,
        name: str,
        expectation_type: str,
        config: Optional[dict] = None,
        severity: str = "warning",
        enabled: bool = True,
    ) -> DataExpectation:
        if not pipeline_id or not pipeline_id.strip():
            raise PipelineDataExpectationError("MISSING_PIPELINE", "pipeline_id is required")
        if not name or not name.strip():
            raise PipelineDataExpectationError("MISSING_NAME", "name is required")
        if expectation_type not in _VALID_EXPECTATION_TYPES:
            raise PipelineDataExpectationError(
                "INVALID_EXPECTATION_TYPE",
                f"expectation_type must be one of {_VALID_EXPECTATION_TYPES}",
            )
        if severity not in _VALID_SEVERITIES:
            raise PipelineDataExpectationError(
                "INVALID_SEVERITY",
                f"severity must be one of {_VALID_SEVERITIES}",
            )

        now = _utcnow()
        eid = f"de-{uuid.uuid4().hex[:8]}"
        expectation = DataExpectation(
            expectation_id=eid,
            pipeline_id=pipeline_id,
            name=name,
            expectation_type=expectation_type,
            config=config,
            severity=severity,
            enabled=enabled,
            last_checked_at=None,
            last_result=None,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            if len(self._expectations) >= _MAX_EXPECTATIONS:
                oldest = min(
                    self._expectations.values(),
                    key=lambda x: x.updated_at or datetime.min,
                )
                del self._expectations[oldest.expectation_id]
            self._expectations[eid] = expectation

        return expectation

    def get_expectation(self, expectation_id: str) -> DataExpectation:
        with self._lock:
            expectation = self._expectations.get(expectation_id)
        if expectation is None:
            raise PipelineDataExpectationError(
                "NOT_FOUND",
                f"expectation {expectation_id} not found",
            )
        return expectation

    def list_expectations(
        self,
        pipeline_id: Optional[str] = None,
        expectation_type: Optional[str] = None,
        severity: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> List[DataExpectation]:
        with self._lock:
            results = list(self._expectations.values())
        if pipeline_id:
            results = [e for e in results if e.pipeline_id == pipeline_id]
        if expectation_type:
            results = [e for e in results if e.expectation_type == expectation_type]
        if severity:
            results = [e for e in results if e.severity == severity]
        if enabled is not None:
            results = [e for e in results if e.enabled == enabled]
        return sorted(
            results,
            key=lambda e: e.updated_at or datetime.min,
            reverse=True,
        )

    def update_expectation(
        self,
        expectation_id: str,
        name: Optional[str] = None,
        config: Optional[dict] = None,
        severity: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> DataExpectation:
        if severity is not None and severity not in _VALID_SEVERITIES:
            raise PipelineDataExpectationError(
                "INVALID_SEVERITY",
                f"severity must be one of {_VALID_SEVERITIES}",
            )

        with self._lock:
            expectation = self._expectations.get(expectation_id)
            if expectation is None:
                raise PipelineDataExpectationError(
                    "NOT_FOUND",
                    f"expectation {expectation_id} not found",
                )

            data = expectation.model_dump()
            if name is not None:
                data["name"] = name
            if config is not None:
                data["config"] = config
            if severity is not None:
                data["severity"] = severity
            if enabled is not None:
                data["enabled"] = enabled
            data["updated_at"] = _utcnow()

            updated = DataExpectation(**data)
            self._expectations[expectation_id] = updated

        return updated

    def delete_expectation(self, expectation_id: str) -> bool:
        with self._lock:
            if expectation_id not in self._expectations:
                return False
            del self._expectations[expectation_id]
        return True

    def run_expectation(self, expectation_id: str) -> DataExpectation:
        with self._lock:
            expectation = self._expectations.get(expectation_id)
            if expectation is None:
                raise PipelineDataExpectationError(
                    "NOT_FOUND",
                    f"expectation {expectation_id} not found",
                )

            now = _utcnow()
            result = "passed" if expectation.expectation_type in (
                ExpectationType.PRIMARY_KEY.value,
                ExpectationType.COLUMN_DISTINCT.value,
            ) else "failed"

            data = expectation.model_dump()
            data["last_checked_at"] = now
            data["last_result"] = result
            data["updated_at"] = now

            updated = DataExpectation(**data)
            self._expectations[expectation_id] = updated

        return updated

    def run_all_expectations(self, pipeline_id: str) -> List[DataExpectation]:
        expectations = self.list_expectations(pipeline_id=pipeline_id, enabled=True)
        results: List[DataExpectation] = []
        for exp in expectations:
            results.append(self.run_expectation(exp.expectation_id))
        return results


_expectation_engine: Optional[PipelineDataExpectationEngine] = None
_expectation_engine_lock = threading.Lock()


def get_expectation_engine() -> PipelineDataExpectationEngine:
    global _expectation_engine
    if _expectation_engine is None:
        with _expectation_engine_lock:
            if _expectation_engine is None:
                _expectation_engine = PipelineDataExpectationEngine.get_instance()
    return _expectation_engine