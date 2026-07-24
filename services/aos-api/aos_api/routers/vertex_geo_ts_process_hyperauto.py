"""W2-BP · Vertex 数字孪生 / 地理时间序列 / Process Mining / Hyperauto 路由（#32 #33 #34 #35）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.vertex_geo_ts_process_hyperauto import (
    CausalAnalysis,
    EventLog,
    IntegrationConfig,
    LocationPoint,
    LocationTrack,
    ProcessFlow,
    SyncRecord,
    TwinModel,
    TwinSimulation,
    VertexGeoTsProcessError,
    get_digital_twin_engine,
    get_geo_time_series_engine,
    get_hyperauto_engine,
    get_process_mining_engine,
)

router = APIRouter(
    prefix="/vertex-geo-ts-process-hyperauto",
    tags=["vertex-geo-ts-process-hyperauto"],
)


def _map_err(err: VertexGeoTsProcessError) -> HTTPException:
    code = getattr(err, "code", "") or ""
    if code == "NOT_FOUND":
        status = 404
    elif code.startswith("INVALID_"):
        status = 400
    else:
        status = 500
    payload = (
        err.error_payload()
        if hasattr(err, "error_payload")
        else {"code": code, "message": str(err)}
    )
    return HTTPException(status_code=status, detail=payload)


# ════════════════════ #32 Digital Twin ════════════════════

class CreateTwinBody(BaseModel):
    name: str
    description: str = ""
    physical_entity_id: str = ""
    state: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None


class RunSimulationBody(BaseModel):
    twin_id: str
    steps: int = 10


class AnalyzeCausalBody(BaseModel):
    twin_id: str
    cause_variable: str
    effect_variable: str
    correlation: float = 0.0
    lag_seconds: int = 0
    description: str = ""


@router.post("/twin/twins", response_model=TwinModel)
def create_twin(body: CreateTwinBody, _=require_principal):
    try:
        return get_digital_twin_engine().create_twin(
            name=body.name,
            description=body.description,
            physical_entity_id=body.physical_entity_id,
            state=body.state,
            parameters=body.parameters,
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/twin/twins/{twin_id}", response_model=TwinModel)
def get_twin(twin_id: str, _=require_principal):
    try:
        return get_digital_twin_engine().get_twin(twin_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/twin/twins", response_model=list[TwinModel])
def list_twins(_=require_principal):
    return get_digital_twin_engine().list_twins()


@router.put("/twin/twins/{twin_id}", response_model=TwinModel)
def update_twin(twin_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_digital_twin_engine().update_twin(twin_id, updates)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.delete("/twin/twins/{twin_id}")
def delete_twin(twin_id: str, _=require_principal):
    deleted = get_digital_twin_engine().delete_twin(twin_id)
    return {"deleted": deleted}


@router.post("/twin/simulations", response_model=TwinSimulation)
def run_simulation(body: RunSimulationBody, _=require_principal):
    try:
        return get_digital_twin_engine().run_simulation(
            twin_id=body.twin_id, steps=body.steps
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/twin/simulations/{simulation_id}", response_model=TwinSimulation)
def get_simulation(simulation_id: str, _=require_principal):
    try:
        return get_digital_twin_engine().get_simulation(simulation_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/twin/simulations", response_model=list[TwinSimulation])
def list_simulations(
    twin_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_digital_twin_engine().list_simulations(
        twin_id=twin_id, status=status
    )


@router.delete("/twin/simulations/{simulation_id}")
def delete_simulation(simulation_id: str, _=require_principal):
    deleted = get_digital_twin_engine().delete_simulation(simulation_id)
    return {"deleted": deleted}


@router.post("/twin/causal", response_model=CausalAnalysis)
def analyze_causality(body: AnalyzeCausalBody, _=require_principal):
    try:
        return get_digital_twin_engine().analyze_causality(
            twin_id=body.twin_id,
            cause_variable=body.cause_variable,
            effect_variable=body.effect_variable,
            correlation=body.correlation,
            lag_seconds=body.lag_seconds,
            description=body.description,
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/twin/causal/{analysis_id}", response_model=CausalAnalysis)
def get_causal_analysis(analysis_id: str, _=require_principal):
    try:
        return get_digital_twin_engine().get_causal_analysis(analysis_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/twin/causal", response_model=list[CausalAnalysis])
def list_causal_analyses(
    twin_id: str | None = Query(None),
    _=require_principal,
):
    return get_digital_twin_engine().list_causal_analyses(twin_id=twin_id)


@router.delete("/twin/causal/{analysis_id}")
def delete_causal_analysis(analysis_id: str, _=require_principal):
    deleted = get_digital_twin_engine().delete_causal_analysis(analysis_id)
    return {"deleted": deleted}


# ════════════════════ #33 Geo Time Series ════════════════════

class CreateTrackBody(BaseModel):
    entity_id: str
    name: str
    sync_enabled: bool = True


class RecordPointBody(BaseModel):
    track_id: str
    latitude: float
    longitude: float
    elevation: float = 0.0
    speed: float = 0.0
    heading: float = 0.0
    metadata: dict[str, Any] | None = None


@router.post("/geo-ts/tracks", response_model=LocationTrack)
def create_track(body: CreateTrackBody, _=require_principal):
    try:
        return get_geo_time_series_engine().create_track(
            entity_id=body.entity_id,
            name=body.name,
            sync_enabled=body.sync_enabled,
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/geo-ts/tracks/{track_id}", response_model=LocationTrack)
def get_track(track_id: str, _=require_principal):
    try:
        return get_geo_time_series_engine().get_track(track_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/geo-ts/tracks", response_model=list[LocationTrack])
def list_tracks(
    entity_id: str | None = Query(None),
    sync_enabled_only: bool = Query(False),
    _=require_principal,
):
    return get_geo_time_series_engine().list_tracks(
        entity_id=entity_id, sync_enabled_only=sync_enabled_only
    )


@router.put("/geo-ts/tracks/{track_id}", response_model=LocationTrack)
def update_track(track_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_geo_time_series_engine().update_track(track_id, updates)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.delete("/geo-ts/tracks/{track_id}")
def delete_track(track_id: str, _=require_principal):
    deleted = get_geo_time_series_engine().delete_track(track_id)
    return {"deleted": deleted}


@router.post("/geo-ts/points", response_model=LocationPoint)
def record_point(body: RecordPointBody, _=require_principal):
    try:
        return get_geo_time_series_engine().record_point(
            track_id=body.track_id,
            latitude=body.latitude,
            longitude=body.longitude,
            elevation=body.elevation,
            speed=body.speed,
            heading=body.heading,
            metadata=body.metadata,
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/geo-ts/points/{point_id}", response_model=LocationPoint)
def get_point(point_id: str, _=require_principal):
    try:
        return get_geo_time_series_engine().get_point(point_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/geo-ts/points", response_model=list[LocationPoint])
def list_points(
    track_id: str | None = Query(None),
    limit: int = Query(100),
    _=require_principal,
):
    return get_geo_time_series_engine().list_points(
        track_id=track_id, limit=limit
    )


@router.get("/geo-ts/tracks/{track_id}/path")
def get_track_path(
    track_id: str,
    limit: int = Query(100),
    _=require_principal,
):
    try:
        return get_geo_time_series_engine().get_track_path(
            track_id=track_id, limit=limit
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.delete("/geo-ts/points/{point_id}")
def delete_point(point_id: str, _=require_principal):
    deleted = get_geo_time_series_engine().delete_point(point_id)
    return {"deleted": deleted}


# ════════════════════ #34 Process Mining ════════════════════

class LogEventBody(BaseModel):
    case_id: str
    activity: str
    resource: str = ""
    cost: float = 0.0
    metadata: dict[str, Any] | None = None


class DiscoverFlowBody(BaseModel):
    name: str
    case_ids: list[str] | None = None


@router.post("/process/events", response_model=EventLog)
def log_event(body: LogEventBody, _=require_principal):
    try:
        return get_process_mining_engine().log_event(
            case_id=body.case_id,
            activity=body.activity,
            resource=body.resource,
            cost=body.cost,
            metadata=body.metadata,
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/process/events/{event_id}", response_model=EventLog)
def get_event(event_id: str, _=require_principal):
    try:
        return get_process_mining_engine().get_event(event_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/process/events", response_model=list[EventLog])
def list_events(
    case_id: str | None = Query(None),
    activity: str | None = Query(None),
    _=require_principal,
):
    return get_process_mining_engine().list_events(
        case_id=case_id, activity=activity
    )


@router.delete("/process/events/{event_id}")
def delete_event(event_id: str, _=require_principal):
    deleted = get_process_mining_engine().delete_event(event_id)
    return {"deleted": deleted}


@router.post("/process/flows/discover", response_model=ProcessFlow)
def discover_flow(body: DiscoverFlowBody, _=require_principal):
    try:
        return get_process_mining_engine().discover_flow(
            name=body.name, case_ids=body.case_ids
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/process/flows/{flow_id}", response_model=ProcessFlow)
def get_flow(flow_id: str, _=require_principal):
    try:
        return get_process_mining_engine().get_flow(flow_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/process/flows", response_model=list[ProcessFlow])
def list_flows(_=require_principal):
    return get_process_mining_engine().list_flows()


@router.get("/process/flows/{flow_id}/analysis")
def get_flow_analysis(flow_id: str, _=require_principal):
    try:
        return get_process_mining_engine().get_flow_analysis(flow_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.delete("/process/flows/{flow_id}")
def delete_flow(flow_id: str, _=require_principal):
    deleted = get_process_mining_engine().delete_flow(flow_id)
    return {"deleted": deleted}


# ════════════════════ #35 Hyperauto ════════════════════

class RegisterIntegrationBody(BaseModel):
    source_system: str
    sync_enabled: bool = True
    auto_ontology_mapping: bool = True
    sync_interval_seconds: int = 300
    config: dict[str, Any] | None = None


class RunSyncBody(BaseModel):
    integration_id: str


@router.post("/hyperauto/integrations", response_model=IntegrationConfig)
def register_integration(body: RegisterIntegrationBody, _=require_principal):
    try:
        return get_hyperauto_engine().register_integration(
            source_system=body.source_system,
            sync_enabled=body.sync_enabled,
            auto_ontology_mapping=body.auto_ontology_mapping,
            sync_interval_seconds=body.sync_interval_seconds,
            config=body.config,
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get(
    "/hyperauto/integrations/{integration_id}", response_model=IntegrationConfig
)
def get_integration(integration_id: str, _=require_principal):
    try:
        return get_hyperauto_engine().get_integration(integration_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get(
    "/hyperauto/integrations", response_model=list[IntegrationConfig]
)
def list_integrations(
    source_system: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_hyperauto_engine().list_integrations(
        source_system=source_system, status=status
    )


@router.put(
    "/hyperauto/integrations/{integration_id}", response_model=IntegrationConfig
)
def update_integration(
    integration_id: str, updates: dict[str, Any], _=require_principal
):
    try:
        return get_hyperauto_engine().update_integration(
            integration_id, updates
        )
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.post(
    "/hyperauto/integrations/{integration_id}/pause",
    response_model=IntegrationConfig,
)
def pause_integration(integration_id: str, _=require_principal):
    try:
        return get_hyperauto_engine().pause_integration(integration_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.post(
    "/hyperauto/integrations/{integration_id}/resume",
    response_model=IntegrationConfig,
)
def resume_integration(integration_id: str, _=require_principal):
    try:
        return get_hyperauto_engine().resume_integration(integration_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.delete("/hyperauto/integrations/{integration_id}")
def delete_integration(integration_id: str, _=require_principal):
    deleted = get_hyperauto_engine().delete_integration(integration_id)
    return {"deleted": deleted}


@router.post("/hyperauto/syncs", response_model=SyncRecord)
def run_sync(body: RunSyncBody, _=require_principal):
    try:
        return get_hyperauto_engine().run_sync(body.integration_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/hyperauto/syncs/{sync_id}", response_model=SyncRecord)
def get_sync(sync_id: str, _=require_principal):
    try:
        return get_hyperauto_engine().get_sync(sync_id)
    except VertexGeoTsProcessError as e:
        raise _map_err(e) from e


@router.get("/hyperauto/syncs", response_model=list[SyncRecord])
def list_syncs(
    integration_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_hyperauto_engine().list_syncs(
        integration_id=integration_id, status=status
    )


@router.delete("/hyperauto/syncs/{sync_id}")
def delete_sync(sync_id: str, _=require_principal):
    deleted = get_hyperauto_engine().delete_sync(sync_id)
    return {"deleted": deleted}
