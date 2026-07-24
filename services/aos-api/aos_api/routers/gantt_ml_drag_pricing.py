"""W2-BM · Gantt / ML Scheduling / Workshop Drag / Compute Pricing 路由（#18 #19 #20 #21）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.gantt_ml_drag_pricing import (
    DragElement,
    DragSession,
    GanttAssignment,
    GanttMlDragPricingError,
    GanttTask,
    MLModel,
    MLPrediction,
    PricingTier,
    UsageMeter,
    get_compute_pricing_engine,
    get_gantt_schedule_engine,
    get_ml_scheduling_engine,
    get_workshop_drag_engine,
)

router = APIRouter(
    prefix="/gantt-ml-drag-pricing",
    tags=["gantt-ml-drag-pricing"],
)


def _map_err(err: GanttMlDragPricingError) -> HTTPException:
    code = getattr(err, "code", "") or ""
    if code == "NOT_FOUND":
        status = 404
    elif (
        code.startswith("INVALID_")
        or code
        in ("DEPENDENCY_VIOLATION", "ELEMENT_LOCKED", "NOT_COMPUTED", "MODEL_NOT_TRAINED")
    ):
        status = 400
    else:
        status = 500
    payload = (
        err.error_payload()
        if hasattr(err, "error_payload")
        else {"code": code, "message": str(err)}
    )
    return HTTPException(status_code=status, detail=payload)


# ════════════════════ #18 Gantt Schedule ════════════════════

class CreateTaskBody(BaseModel):
    name: str
    start_time: float
    end_time: float
    resource_id: str = ""
    dependencies: list[str] = []
    constraints: dict[str, Any] = {}


class MoveTaskBody(BaseModel):
    new_start_time: float


class CreateAssignmentBody(BaseModel):
    task_id: str
    resource_id: str
    allocation_percent: float = 100.0
    suggested: bool = False


@router.post("/gantt/tasks", response_model=GanttTask)
def create_task(body: CreateTaskBody, _=require_principal):
    try:
        return get_gantt_schedule_engine().create_task(
            name=body.name,
            start_time=body.start_time,
            end_time=body.end_time,
            resource_id=body.resource_id,
            dependencies=body.dependencies,
            constraints=body.constraints,
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/gantt/tasks/{task_id}", response_model=GanttTask)
def get_task(task_id: str, _=require_principal):
    try:
        return get_gantt_schedule_engine().get_task(task_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/gantt/tasks", response_model=list[GanttTask])
def list_tasks(
    resource_id: str | None = Query(None),
    _=require_principal,
):
    return get_gantt_schedule_engine().list_tasks(resource_id=resource_id)


@router.put("/gantt/tasks/{task_id}", response_model=GanttTask)
def update_task(task_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_gantt_schedule_engine().update_task(task_id, updates)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.post("/gantt/tasks/{task_id}/move", response_model=GanttTask)
def move_task(task_id: str, body: MoveTaskBody, _=require_principal):
    try:
        return get_gantt_schedule_engine().move_task(task_id, body.new_start_time)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.delete("/gantt/tasks/{task_id}")
def delete_task(task_id: str, _=require_principal):
    deleted = get_gantt_schedule_engine().delete_task(task_id)
    return {"deleted": deleted}


@router.post("/gantt/assignments", response_model=GanttAssignment)
def create_assignment(body: CreateAssignmentBody, _=require_principal):
    try:
        return get_gantt_schedule_engine().assign_resource(
            task_id=body.task_id,
            resource_id=body.resource_id,
            allocation_percent=body.allocation_percent,
            suggested=body.suggested,
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.post("/gantt/tasks/{task_id}/suggest-assignment", response_model=GanttAssignment)
def suggest_assignment(task_id: str, _=require_principal):
    try:
        return get_gantt_schedule_engine().suggest_assignment(task_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/gantt/assignments/{assignment_id}", response_model=GanttAssignment)
def get_assignment(assignment_id: str, _=require_principal):
    try:
        return get_gantt_schedule_engine().get_assignment(assignment_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/gantt/assignments", response_model=list[GanttAssignment])
def list_assignments(
    task_id: str | None = Query(None),
    resource_id: str | None = Query(None),
    _=require_principal,
):
    return get_gantt_schedule_engine().list_assignments(
        task_id=task_id, resource_id=resource_id
    )


@router.delete("/gantt/assignments/{assignment_id}")
def delete_assignment(assignment_id: str, _=require_principal):
    deleted = get_gantt_schedule_engine().delete_assignment(assignment_id)
    return {"deleted": deleted}


# ════════════════════ #19 ML Scheduling ════════════════════

class RegisterModelBody(BaseModel):
    name: str
    algorithm: str
    features: list[str] = []


class TrainModelBody(BaseModel):
    accuracy: float


class PredictBody(BaseModel):
    model_id: str
    predicted_resource_id: str
    predicted_value: float
    confidence: float = 0.0
    horizon_seconds: int = 3600
    metadata: dict[str, Any] | None = None


@router.post("/ml/models", response_model=MLModel)
def register_model(body: RegisterModelBody, _=require_principal):
    try:
        return get_ml_scheduling_engine().register_model(
            name=body.name,
            algorithm=body.algorithm,
            features=body.features,
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/ml/models/{model_id}", response_model=MLModel)
def get_model(model_id: str, _=require_principal):
    try:
        return get_ml_scheduling_engine().get_model(model_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/ml/models", response_model=list[MLModel])
def list_models(
    algorithm: str | None = Query(None),
    trained_only: bool = Query(False),
    _=require_principal,
):
    return get_ml_scheduling_engine().list_models(
        algorithm=algorithm, trained_only=trained_only
    )


@router.post("/ml/models/{model_id}/train", response_model=MLModel)
def train_model(model_id: str, body: TrainModelBody, _=require_principal):
    try:
        return get_ml_scheduling_engine().train_model(model_id, body.accuracy)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.put("/ml/models/{model_id}", response_model=MLModel)
def update_model(model_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_ml_scheduling_engine().update_model(model_id, updates)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.delete("/ml/models/{model_id}")
def delete_model(model_id: str, _=require_principal):
    deleted = get_ml_scheduling_engine().delete_model(model_id)
    return {"deleted": deleted}


@router.post("/ml/predict", response_model=MLPrediction)
def predict(body: PredictBody, _=require_principal):
    try:
        return get_ml_scheduling_engine().predict(
            model_id=body.model_id,
            predicted_resource_id=body.predicted_resource_id,
            predicted_value=body.predicted_value,
            confidence=body.confidence,
            horizon_seconds=body.horizon_seconds,
            metadata=body.metadata,
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/ml/predictions/{prediction_id}", response_model=MLPrediction)
def get_prediction(prediction_id: str, _=require_principal):
    try:
        return get_ml_scheduling_engine().get_prediction(prediction_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/ml/predictions", response_model=list[MLPrediction])
def list_predictions(
    model_id: str | None = Query(None),
    resource_id: str | None = Query(None),
    _=require_principal,
):
    return get_ml_scheduling_engine().list_predictions(
        model_id=model_id, resource_id=resource_id
    )


@router.delete("/ml/predictions/{prediction_id}")
def delete_prediction(prediction_id: str, _=require_principal):
    deleted = get_ml_scheduling_engine().delete_prediction(prediction_id)
    return {"deleted": deleted}


# ════════════════════ #20 Workshop Drag ════════════════════

class CreateElementBody(BaseModel):
    element_type: str
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 50
    rotation: float = 0
    z_index: int = 0
    metadata: dict[str, Any] | None = None


class MoveElementBody(BaseModel):
    x: float
    y: float


class ResizeElementBody(BaseModel):
    width: float
    height: float


class RotateElementBody(BaseModel):
    rotation: float


class CreateSessionBody(BaseModel):
    canvas_id: str
    user_id: str


class AddElementToSessionBody(BaseModel):
    element_id: str


@router.post("/drag/elements", response_model=DragElement)
def create_element(body: CreateElementBody, _=require_principal):
    try:
        return get_workshop_drag_engine().create_element(
            element_type=body.element_type,
            x=body.x,
            y=body.y,
            width=body.width,
            height=body.height,
            rotation=body.rotation,
            z_index=body.z_index,
            metadata=body.metadata,
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/drag/elements/{element_id}", response_model=DragElement)
def get_element(element_id: str, _=require_principal):
    try:
        return get_workshop_drag_engine().get_element(element_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/drag/elements", response_model=list[DragElement])
def list_elements(
    element_type: str | None = Query(None),
    _=require_principal,
):
    return get_workshop_drag_engine().list_elements(element_type=element_type)


@router.post("/drag/elements/{element_id}/move", response_model=DragElement)
def move_element(element_id: str, body: MoveElementBody, _=require_principal):
    try:
        return get_workshop_drag_engine().move_element(element_id, body.x, body.y)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.post("/drag/elements/{element_id}/resize", response_model=DragElement)
def resize_element(element_id: str, body: ResizeElementBody, _=require_principal):
    try:
        return get_workshop_drag_engine().resize_element(
            element_id, body.width, body.height
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.post("/drag/elements/{element_id}/rotate", response_model=DragElement)
def rotate_element(element_id: str, body: RotateElementBody, _=require_principal):
    try:
        return get_workshop_drag_engine().rotate_element(element_id, body.rotation)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.post("/drag/elements/{element_id}/lock", response_model=DragElement)
def lock_element(element_id: str, _=require_principal):
    try:
        return get_workshop_drag_engine().lock_element(element_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.post("/drag/elements/{element_id}/unlock", response_model=DragElement)
def unlock_element(element_id: str, _=require_principal):
    try:
        return get_workshop_drag_engine().unlock_element(element_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.delete("/drag/elements/{element_id}")
def delete_element(element_id: str, _=require_principal):
    deleted = get_workshop_drag_engine().delete_element(element_id)
    return {"deleted": deleted}


@router.post("/drag/sessions", response_model=DragSession)
def create_session(body: CreateSessionBody, _=require_principal):
    try:
        return get_workshop_drag_engine().create_session(
            canvas_id=body.canvas_id, user_id=body.user_id
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/drag/sessions/{session_id}", response_model=DragSession)
def get_session(session_id: str, _=require_principal):
    try:
        return get_workshop_drag_engine().get_session(session_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/drag/sessions", response_model=list[DragSession])
def list_sessions(
    canvas_id: str | None = Query(None),
    active_only: bool = Query(False),
    _=require_principal,
):
    return get_workshop_drag_engine().list_sessions(
        canvas_id=canvas_id, active_only=active_only
    )


@router.post("/drag/sessions/{session_id}/elements", response_model=DragSession)
def add_element_to_session(
    session_id: str, body: AddElementToSessionBody, _=require_principal
):
    try:
        return get_workshop_drag_engine().add_element_to_session(
            session_id, body.element_id
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.post("/drag/sessions/{session_id}/close", response_model=DragSession)
def close_session(session_id: str, _=require_principal):
    try:
        return get_workshop_drag_engine().close_session(session_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.delete("/drag/sessions/{session_id}")
def delete_session(session_id: str, _=require_principal):
    deleted = get_workshop_drag_engine().delete_session(session_id)
    return {"deleted": deleted}


# ════════════════════ #21 Compute Pricing ════════════════════

class SetPricingBody(BaseModel):
    resource_type: str
    price_per_second: float
    currency: str = "USD"
    min_charge_seconds: int = 1
    description: str = ""


class StartMeteringBody(BaseModel):
    session_id: str
    resource_type: str


@router.post("/pricing/tiers", response_model=PricingTier)
def set_pricing(body: SetPricingBody, _=require_principal):
    try:
        return get_compute_pricing_engine().set_pricing(
            resource_type=body.resource_type,
            price_per_second=body.price_per_second,
            currency=body.currency,
            min_charge_seconds=body.min_charge_seconds,
            description=body.description,
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/pricing/tiers/{resource_type}", response_model=PricingTier)
def get_pricing(resource_type: str, _=require_principal):
    try:
        return get_compute_pricing_engine().get_pricing(resource_type)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/pricing/tiers", response_model=list[PricingTier])
def list_pricing(_=require_principal):
    return get_compute_pricing_engine().list_pricing()


@router.delete("/pricing/tiers/{resource_type}")
def delete_pricing(resource_type: str, _=require_principal):
    deleted = get_compute_pricing_engine().delete_pricing(resource_type)
    return {"deleted": deleted}


@router.post("/pricing/meters/start", response_model=UsageMeter)
def start_metering(body: StartMeteringBody, _=require_principal):
    try:
        return get_compute_pricing_engine().start_metering(
            session_id=body.session_id,
            resource_type=body.resource_type,
        )
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.post("/pricing/meters/{meter_id}/stop", response_model=UsageMeter)
def stop_metering(meter_id: str, _=require_principal):
    try:
        return get_compute_pricing_engine().stop_metering(meter_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/pricing/meters/{meter_id}", response_model=UsageMeter)
def get_meter(meter_id: str, _=require_principal):
    try:
        return get_compute_pricing_engine().get_meter(meter_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/pricing/meters", response_model=list[UsageMeter])
def list_meters(
    session_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_compute_pricing_engine().list_meters(
        session_id=session_id, status=status
    )


@router.post("/pricing/meters/{meter_id}/bill", response_model=UsageMeter)
def bill_meter(meter_id: str, _=require_principal):
    try:
        return get_compute_pricing_engine().bill_meter(meter_id)
    except GanttMlDragPricingError as e:
        raise _map_err(e) from e


@router.get("/pricing/summary/{session_id}")
def get_usage_summary(session_id: str, _=require_principal):
    return get_compute_pricing_engine().get_usage_summary(session_id)


@router.delete("/pricing/meters/{meter_id}")
def delete_meter(meter_id: str, _=require_principal):
    deleted = get_compute_pricing_engine().delete_meter(meter_id)
    return {"deleted": deleted}
