"""W2-BM · Gantt / ML Scheduling / Workshop Drag / Compute Pricing 引擎组（#18 #19 #20 #21）.

本模块提供 W2+ 低优先级批次的 4 个内存态引擎：
    - GanttScheduleEngine     #18 Dynamic Scheduling 甘特图
    - MLSchedulingEngine       #19 Dynamic Scheduling 机器学习
    - WorkshopDragEngine       #20 Workshop 拖拽
    - ComputePricingEngine     #21 计算秒定价 + 用量计量

所有引擎均线程安全（threading.Lock），容量上限 200，FIFO 按时间戳淘汰。
"""
from __future__ import annotations

import threading
import time
import uuid
import random
from typing import Any

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class GanttMlDragPricingError(Exception):
    """Gantt / ML / Drag / Pricing 引擎统一错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def error_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


# ════════════════════ #18 Gantt Schedule ════════════════════

class GanttTask(BaseModel):
    id: str = Field(default_factory=lambda: _uid("gtask"))
    name: str
    start_time: float
    end_time: float
    resource_id: str = ""
    progress: float = 0.0
    dependencies: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    color: str = "#3b82f6"
    created_at: float = Field(default_factory=_now_ts)


class GanttAssignment(BaseModel):
    id: str = Field(default_factory=lambda: _uid("gassign"))
    task_id: str
    resource_id: str
    allocation_percent: float = 100.0
    suggested: bool = False
    created_at: float = Field(default_factory=_now_ts)


class GanttScheduleEngine:
    """#18 Dynamic Scheduling 甘特图引擎。"""

    _MAX_TASKS = 200
    _MAX_ASSIGNMENTS = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, GanttTask] = {}
        self._assignments: dict[str, GanttAssignment] = {}

    def _evict_tasks(self) -> None:
        if len(self._tasks) >= self._MAX_TASKS:
            oldest_id = min(
                self._tasks, key=lambda tid: self._tasks[tid].created_at
            )
            del self._tasks[oldest_id]

    def _evict_assignments(self) -> None:
        if len(self._assignments) >= self._MAX_ASSIGNMENTS:
            oldest_id = min(
                self._assignments,
                key=lambda aid: self._assignments[aid].created_at,
            )
            del self._assignments[oldest_id]

    def create_task(
        self,
        name: str,
        start_time: float,
        end_time: float,
        resource_id: str = "",
        dependencies: list[str] | None = None,
        constraints: dict | None = None,
    ) -> GanttTask:
        if end_time <= start_time:
            raise GanttMlDragPricingError(
                "INVALID_TIME_RANGE",
                "end_time must be greater than start_time",
            )
        task = GanttTask(
            name=name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            dependencies=dependencies or [],
            constraints=constraints or {},
        )
        with self._lock:
            self._evict_tasks()
            self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> GanttTask:
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            raise GanttMlDragPricingError("NOT_FOUND", f"task {task_id} not found")
        return task

    def list_tasks(self, resource_id: str | None = None) -> list[GanttTask]:
        with self._lock:
            results = list(self._tasks.values())
        if resource_id is not None:
            results = [t for t in results if t.resource_id == resource_id]
        return sorted(results, key=lambda t: t.created_at)

    def update_task(self, task_id: str, updates: dict[str, Any]) -> GanttTask:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"task {task_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(task).model_fields
            }
            updated = task.model_copy(update=applicable)
            self._tasks[task_id] = updated
        return updated

    def move_task(self, task_id: str, new_start_time: float) -> GanttTask:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"task {task_id} not found"
                )
            duration = task.end_time - task.start_time
            for dep_id in task.dependencies:
                dep = self._tasks.get(dep_id)
                if dep is not None and dep.end_time > new_start_time:
                    raise GanttMlDragPricingError(
                        "DEPENDENCY_VIOLATION",
                        f"dependency {dep_id} ends at {dep.end_time}, "
                        f"after new start_time {new_start_time}",
                    )
            updated = task.model_copy(
                update={
                    "start_time": new_start_time,
                    "end_time": new_start_time + duration,
                }
            )
            self._tasks[task_id] = updated
        return updated

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def assign_resource(
        self,
        task_id: str,
        resource_id: str,
        allocation_percent: float = 100.0,
        suggested: bool = False,
    ) -> GanttAssignment:
        assignment = GanttAssignment(
            task_id=task_id,
            resource_id=resource_id,
            allocation_percent=allocation_percent,
            suggested=suggested,
        )
        with self._lock:
            self._evict_assignments()
            self._assignments[assignment.id] = assignment
        return assignment

    def suggest_assignment(self, task_id: str) -> GanttAssignment:
        return self.assign_resource(
            task_id=task_id,
            resource_id=f"resource-{random.randint(1, 100)}",
            allocation_percent=100.0,
            suggested=True,
        )

    def get_assignment(self, assignment_id: str) -> GanttAssignment:
        with self._lock:
            assignment = self._assignments.get(assignment_id)
        if assignment is None:
            raise GanttMlDragPricingError(
                "NOT_FOUND", f"assignment {assignment_id} not found"
            )
        return assignment

    def list_assignments(
        self,
        task_id: str | None = None,
        resource_id: str | None = None,
    ) -> list[GanttAssignment]:
        with self._lock:
            results = list(self._assignments.values())
        if task_id is not None:
            results = [a for a in results if a.task_id == task_id]
        if resource_id is not None:
            results = [a for a in results if a.resource_id == resource_id]
        return sorted(results, key=lambda a: a.created_at)

    def delete_assignment(self, assignment_id: str) -> bool:
        with self._lock:
            return self._assignments.pop(assignment_id, None) is not None


# ════════════════════ #19 ML Scheduling ════════════════════

class MLModel(BaseModel):
    id: str = Field(default_factory=lambda: _uid("ml"))
    name: str
    algorithm: str  # regression / lstm / arima / transformer
    features: list[str] = Field(default_factory=list)
    accuracy: float = 0.0
    trained: bool = False
    created_at: float = Field(default_factory=_now_ts)


class MLPrediction(BaseModel):
    id: str = Field(default_factory=lambda: _uid("pred"))
    model_id: str
    predicted_resource_id: str
    predicted_at: float = Field(default_factory=_now_ts)
    predicted_value: float
    confidence: float = 0.0
    horizon_seconds: int = 3600
    metadata: dict[str, Any] = Field(default_factory=dict)


class MLSchedulingEngine:
    """#19 Dynamic Scheduling 机器学习引擎。"""

    _MAX_MODELS = 200
    _MAX_PREDICTIONS = 200
    _VALID_ALGORITHMS = {"regression", "lstm", "arima", "transformer"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._models: dict[str, MLModel] = {}
        self._predictions: dict[str, MLPrediction] = {}

    def _evict_models(self) -> None:
        if len(self._models) >= self._MAX_MODELS:
            oldest_id = min(
                self._models, key=lambda mid: self._models[mid].created_at
            )
            del self._models[oldest_id]

    def _evict_predictions(self) -> None:
        if len(self._predictions) >= self._MAX_PREDICTIONS:
            oldest_id = min(
                self._predictions,
                key=lambda pid: self._predictions[pid].predicted_at,
            )
            del self._predictions[oldest_id]

    def register_model(
        self,
        name: str,
        algorithm: str,
        features: list[str] | None = None,
    ) -> MLModel:
        if algorithm not in self._VALID_ALGORITHMS:
            raise GanttMlDragPricingError(
                "INVALID_ALGORITHM",
                f"algorithm must be one of {sorted(self._VALID_ALGORITHMS)}",
            )
        model = MLModel(
            name=name,
            algorithm=algorithm,
            features=features or [],
        )
        with self._lock:
            self._evict_models()
            self._models[model.id] = model
        return model

    def get_model(self, model_id: str) -> MLModel:
        with self._lock:
            model = self._models.get(model_id)
        if model is None:
            raise GanttMlDragPricingError("NOT_FOUND", f"model {model_id} not found")
        return model

    def list_models(
        self,
        algorithm: str | None = None,
        trained_only: bool = False,
    ) -> list[MLModel]:
        with self._lock:
            results = list(self._models.values())
        if algorithm is not None:
            results = [m for m in results if m.algorithm == algorithm]
        if trained_only:
            results = [m for m in results if m.trained]
        return sorted(results, key=lambda m: m.created_at)

    def train_model(self, model_id: str, accuracy: float) -> MLModel:
        if accuracy < 0 or accuracy > 1:
            raise GanttMlDragPricingError(
                "INVALID_ACCURACY", "accuracy must be between 0 and 1"
            )
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"model {model_id} not found"
                )
            updated = model.model_copy(
                update={"trained": True, "accuracy": accuracy}
            )
            self._models[model_id] = updated
        return updated

    def update_model(self, model_id: str, updates: dict[str, Any]) -> MLModel:
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"model {model_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(model).model_fields
            }
            updated = model.model_copy(update=applicable)
            self._models[model_id] = updated
        return updated

    def delete_model(self, model_id: str) -> bool:
        with self._lock:
            return self._models.pop(model_id, None) is not None

    def predict(
        self,
        model_id: str,
        predicted_resource_id: str,
        predicted_value: float,
        confidence: float = 0.0,
        horizon_seconds: int = 3600,
        metadata: dict | None = None,
    ) -> MLPrediction:
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"model {model_id} not found"
                )
            if not model.trained:
                raise GanttMlDragPricingError(
                    "MODEL_NOT_TRAINED",
                    f"model {model_id} is not trained",
                )
        prediction = MLPrediction(
            model_id=model_id,
            predicted_resource_id=predicted_resource_id,
            predicted_value=predicted_value,
            confidence=confidence,
            horizon_seconds=horizon_seconds,
            metadata=metadata or {},
        )
        with self._lock:
            self._evict_predictions()
            self._predictions[prediction.id] = prediction
        return prediction

    def get_prediction(self, prediction_id: str) -> MLPrediction:
        with self._lock:
            prediction = self._predictions.get(prediction_id)
        if prediction is None:
            raise GanttMlDragPricingError(
                "NOT_FOUND", f"prediction {prediction_id} not found"
            )
        return prediction

    def list_predictions(
        self,
        model_id: str | None = None,
        resource_id: str | None = None,
    ) -> list[MLPrediction]:
        with self._lock:
            results = list(self._predictions.values())
        if model_id is not None:
            results = [p for p in results if p.model_id == model_id]
        if resource_id is not None:
            results = [p for p in results if p.predicted_resource_id == resource_id]
        return sorted(results, key=lambda p: p.predicted_at)

    def delete_prediction(self, prediction_id: str) -> bool:
        with self._lock:
            return self._predictions.pop(prediction_id, None) is not None


# ════════════════════ #20 Workshop Drag ════════════════════

class DragElement(BaseModel):
    id: str = Field(default_factory=lambda: _uid("elem"))
    element_type: str  # node / edge / port / label
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 50.0
    rotation: float = 0.0
    z_index: int = 0
    locked: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=_now_ts)


class DragSession(BaseModel):
    id: str = Field(default_factory=lambda: _uid("session"))
    canvas_id: str
    user_id: str
    elements: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: float = Field(default_factory=_now_ts)


class WorkshopDragEngine:
    """#20 Workshop 拖拽引擎。"""

    _MAX_ELEMENTS = 200
    _MAX_SESSIONS = 200
    _VALID_ELEMENT_TYPES = {"node", "edge", "port", "label"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._elements: dict[str, DragElement] = {}
        self._sessions: dict[str, DragSession] = {}

    def _evict_elements(self) -> None:
        if len(self._elements) >= self._MAX_ELEMENTS:
            oldest_id = min(
                self._elements, key=lambda eid: self._elements[eid].created_at
            )
            del self._elements[oldest_id]

    def _evict_sessions(self) -> None:
        if len(self._sessions) >= self._MAX_SESSIONS:
            oldest_id = min(
                self._sessions, key=lambda sid: self._sessions[sid].created_at
            )
            del self._sessions[oldest_id]

    def create_element(
        self,
        element_type: str,
        x: float = 0,
        y: float = 0,
        width: float = 100,
        height: float = 50,
        rotation: float = 0,
        z_index: int = 0,
        metadata: dict | None = None,
    ) -> DragElement:
        if element_type not in self._VALID_ELEMENT_TYPES:
            raise GanttMlDragPricingError(
                "INVALID_ELEMENT_TYPE",
                f"element_type must be one of {sorted(self._VALID_ELEMENT_TYPES)}",
            )
        element = DragElement(
            element_type=element_type,
            x=x,
            y=y,
            width=width,
            height=height,
            rotation=rotation,
            z_index=z_index,
            metadata=metadata or {},
        )
        with self._lock:
            self._evict_elements()
            self._elements[element.id] = element
        return element

    def get_element(self, element_id: str) -> DragElement:
        with self._lock:
            element = self._elements.get(element_id)
        if element is None:
            raise GanttMlDragPricingError(
                "NOT_FOUND", f"element {element_id} not found"
            )
        return element

    def list_elements(self, element_type: str | None = None) -> list[DragElement]:
        with self._lock:
            results = list(self._elements.values())
        if element_type is not None:
            results = [e for e in results if e.element_type == element_type]
        return sorted(results, key=lambda e: e.created_at)

    def move_element(self, element_id: str, x: float, y: float) -> DragElement:
        with self._lock:
            element = self._elements.get(element_id)
            if element is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"element {element_id} not found"
                )
            if element.locked:
                raise GanttMlDragPricingError(
                    "ELEMENT_LOCKED", f"element {element_id} is locked"
                )
            updated = element.model_copy(update={"x": x, "y": y})
            self._elements[element_id] = updated
        return updated

    def resize_element(
        self, element_id: str, width: float, height: float
    ) -> DragElement:
        with self._lock:
            element = self._elements.get(element_id)
            if element is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"element {element_id} not found"
                )
            updated = element.model_copy(update={"width": width, "height": height})
            self._elements[element_id] = updated
        return updated

    def rotate_element(self, element_id: str, rotation: float) -> DragElement:
        with self._lock:
            element = self._elements.get(element_id)
            if element is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"element {element_id} not found"
                )
            updated = element.model_copy(update={"rotation": rotation})
            self._elements[element_id] = updated
        return updated

    def lock_element(self, element_id: str) -> DragElement:
        with self._lock:
            element = self._elements.get(element_id)
            if element is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"element {element_id} not found"
                )
            updated = element.model_copy(update={"locked": True})
            self._elements[element_id] = updated
        return updated

    def unlock_element(self, element_id: str) -> DragElement:
        with self._lock:
            element = self._elements.get(element_id)
            if element is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"element {element_id} not found"
                )
            updated = element.model_copy(update={"locked": False})
            self._elements[element_id] = updated
        return updated

    def delete_element(self, element_id: str) -> bool:
        with self._lock:
            return self._elements.pop(element_id, None) is not None

    def create_session(self, canvas_id: str, user_id: str) -> DragSession:
        session = DragSession(canvas_id=canvas_id, user_id=user_id)
        with self._lock:
            self._evict_sessions()
            self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> DragSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise GanttMlDragPricingError(
                "NOT_FOUND", f"session {session_id} not found"
            )
        return session

    def list_sessions(
        self,
        canvas_id: str | None = None,
        active_only: bool = False,
    ) -> list[DragSession]:
        with self._lock:
            results = list(self._sessions.values())
        if canvas_id is not None:
            results = [s for s in results if s.canvas_id == canvas_id]
        if active_only:
            results = [s for s in results if s.active]
        return sorted(results, key=lambda s: s.created_at)

    def add_element_to_session(
        self, session_id: str, element_id: str
    ) -> DragSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"session {session_id} not found"
                )
            elements = list(session.elements)
            if element_id not in elements:
                elements.append(element_id)
            updated = session.model_copy(update={"elements": elements})
            self._sessions[session_id] = updated
        return updated

    def close_session(self, session_id: str) -> DragSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"session {session_id} not found"
                )
            updated = session.model_copy(update={"active": False})
            self._sessions[session_id] = updated
        return updated

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None


# ════════════════════ #21 Compute Pricing ════════════════════

class PricingTier(BaseModel):
    id: str = Field(default_factory=lambda: _uid("tier"))
    resource_type: str  # vcpu / gpu_t4 / gpu_v100 / gpu_a10g
    price_per_second: float
    currency: str = "USD"
    min_charge_seconds: int = 1
    description: str = ""
    created_at: float = Field(default_factory=_now_ts)


class UsageMeter(BaseModel):
    id: str = Field(default_factory=lambda: _uid("meter"))
    session_id: str
    resource_type: str
    start_time: float
    end_time: float = 0
    duration_seconds: int = 0
    cost: float = 0.0
    currency: str = "USD"
    status: str  # running / computed / billed
    created_at: float = Field(default_factory=_now_ts)


class ComputePricingEngine:
    """#21 计算秒定价 + 用量计量引擎。"""

    _MAX_TIERS = 200
    _MAX_METERS = 200
    _VALID_RESOURCE_TYPES = {"vcpu", "gpu_t4", "gpu_v100", "gpu_a10g"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tiers: dict[str, PricingTier] = {}
        self._meters: dict[str, UsageMeter] = {}

    def _evict_tiers(self) -> None:
        if len(self._tiers) >= self._MAX_TIERS:
            oldest_id = min(
                self._tiers, key=lambda rt: self._tiers[rt].created_at
            )
            del self._tiers[oldest_id]

    def _evict_meters(self) -> None:
        if len(self._meters) >= self._MAX_METERS:
            oldest_id = min(
                self._meters, key=lambda mid: self._meters[mid].created_at
            )
            del self._meters[oldest_id]

    def set_pricing(
        self,
        resource_type: str,
        price_per_second: float,
        currency: str = "USD",
        min_charge_seconds: int = 1,
        description: str = "",
    ) -> PricingTier:
        if resource_type not in self._VALID_RESOURCE_TYPES:
            raise GanttMlDragPricingError(
                "INVALID_RESOURCE_TYPE",
                f"resource_type must be one of {sorted(self._VALID_RESOURCE_TYPES)}",
            )
        if price_per_second < 0:
            raise GanttMlDragPricingError(
                "INVALID_PRICE", "price_per_second must be >= 0"
            )
        tier = PricingTier(
            resource_type=resource_type,
            price_per_second=price_per_second,
            currency=currency,
            min_charge_seconds=min_charge_seconds,
            description=description,
        )
        with self._lock:
            self._evict_tiers()
            self._tiers[resource_type] = tier
        return tier

    def get_pricing(self, resource_type: str) -> PricingTier:
        with self._lock:
            tier = self._tiers.get(resource_type)
        if tier is None:
            raise GanttMlDragPricingError(
                "NOT_FOUND", f"pricing for {resource_type} not found"
            )
        return tier

    def list_pricing(self) -> list[PricingTier]:
        with self._lock:
            results = list(self._tiers.values())
        return sorted(results, key=lambda t: t.created_at)

    def delete_pricing(self, resource_type: str) -> bool:
        with self._lock:
            return self._tiers.pop(resource_type, None) is not None

    def start_metering(self, session_id: str, resource_type: str) -> UsageMeter:
        with self._lock:
            tier = self._tiers.get(resource_type)
            if tier is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"pricing for {resource_type} not found"
                )
            currency = tier.currency
        meter = UsageMeter(
            session_id=session_id,
            resource_type=resource_type,
            start_time=_now_ts(),
            currency=currency,
            status="running",
        )
        with self._lock:
            self._evict_meters()
            self._meters[meter.id] = meter
        return meter

    def stop_metering(self, meter_id: str) -> UsageMeter:
        with self._lock:
            meter = self._meters.get(meter_id)
            if meter is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"meter {meter_id} not found"
                )
            tier = self._tiers.get(meter.resource_type)
            if tier is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"pricing for {meter.resource_type} not found"
                )
            end_time = _now_ts()
            duration_seconds = int(end_time - meter.start_time)
            if duration_seconds < tier.min_charge_seconds:
                duration_seconds = tier.min_charge_seconds
            cost = duration_seconds * tier.price_per_second
            updated = meter.model_copy(
                update={
                    "end_time": end_time,
                    "duration_seconds": duration_seconds,
                    "cost": cost,
                    "status": "computed",
                }
            )
            self._meters[meter_id] = updated
        return updated

    def get_meter(self, meter_id: str) -> UsageMeter:
        with self._lock:
            meter = self._meters.get(meter_id)
        if meter is None:
            raise GanttMlDragPricingError(
                "NOT_FOUND", f"meter {meter_id} not found"
            )
        return meter

    def list_meters(
        self,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[UsageMeter]:
        with self._lock:
            results = list(self._meters.values())
        if session_id is not None:
            results = [m for m in results if m.session_id == session_id]
        if status is not None:
            results = [m for m in results if m.status == status]
        return sorted(results, key=lambda m: m.created_at)

    def bill_meter(self, meter_id: str) -> UsageMeter:
        with self._lock:
            meter = self._meters.get(meter_id)
            if meter is None:
                raise GanttMlDragPricingError(
                    "NOT_FOUND", f"meter {meter_id} not found"
                )
            if meter.status != "computed":
                raise GanttMlDragPricingError(
                    "NOT_COMPUTED",
                    f"meter {meter_id} status is {meter.status}, must be computed",
                )
            updated = meter.model_copy(update={"status": "billed"})
            self._meters[meter_id] = updated
        return updated

    def get_usage_summary(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            meters = [
                m for m in self._meters.values() if m.session_id == session_id
            ]
        total_cost = 0.0
        total_seconds = 0
        by_resource: dict[str, dict[str, Any]] = {}
        for m in meters:
            total_cost += m.cost
            total_seconds += m.duration_seconds
            bucket = by_resource.setdefault(
                m.resource_type, {"seconds": 0, "cost": 0.0}
            )
            bucket["seconds"] += m.duration_seconds
            bucket["cost"] += m.cost
        return {
            "session_id": session_id,
            "total_cost": total_cost,
            "total_seconds": total_seconds,
            "by_resource": by_resource,
            "meter_count": len(meters),
        }

    def delete_meter(self, meter_id: str) -> bool:
        with self._lock:
            return self._meters.pop(meter_id, None) is not None


# ────────────────────────────────────────────────────────────────
# 单例 getter（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_gantt_engine: GanttScheduleEngine | None = None
_ml_engine: MLSchedulingEngine | None = None
_drag_engine: WorkshopDragEngine | None = None
_pricing_engine: ComputePricingEngine | None = None


def get_gantt_schedule_engine() -> GanttScheduleEngine:
    global _gantt_engine
    if _gantt_engine is None:
        with _lock:
            if _gantt_engine is None:
                _gantt_engine = GanttScheduleEngine()
    return _gantt_engine


def get_ml_scheduling_engine() -> MLSchedulingEngine:
    global _ml_engine
    if _ml_engine is None:
        with _lock:
            if _ml_engine is None:
                _ml_engine = MLSchedulingEngine()
    return _ml_engine


def get_workshop_drag_engine() -> WorkshopDragEngine:
    global _drag_engine
    if _drag_engine is None:
        with _lock:
            if _drag_engine is None:
                _drag_engine = WorkshopDragEngine()
    return _drag_engine


def get_compute_pricing_engine() -> ComputePricingEngine:
    global _pricing_engine
    if _pricing_engine is None:
        with _lock:
            if _pricing_engine is None:
                _pricing_engine = ComputePricingEngine()
    return _pricing_engine
