"""W2-BO · Distributed Tracing / Pipeline Perf / Geospatial / Map Visualization 路由（#26 #27 #30 #31）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.tracing_perf_geo_map import (
    GeoFeature,
    GeoQuery,
    MapLayer,
    MapTemplate,
    PerfBenchmark,
    PerfProfile,
    TraceContext,
    TraceSpan,
    TracingPerfGeoMapError,
    get_distributed_tracing_engine,
    get_geospatial_engine,
    get_map_visualization_engine,
    get_pipeline_perf_engine,
)

router = APIRouter(
    prefix="/tracing-perf-geo-map",
    tags=["tracing-perf-geo-map"],
)


def _map_err(err: TracingPerfGeoMapError) -> HTTPException:
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


# ════════════════════ #26 Distributed Tracing ════════════════════

class StartTraceBody(BaseModel):
    operation_name: str
    service_name: str
    attributes: dict[str, Any] | None = None


class StartSpanBody(BaseModel):
    trace_id: str
    operation_name: str
    service_name: str
    parent_span_id: str = ""
    attributes: dict[str, Any] | None = None


class FinishSpanBody(BaseModel):
    status: str = "completed"
    events: list[dict[str, Any]] | None = None


class AddEventBody(BaseModel):
    event: dict[str, Any]


class FinishTraceBody(BaseModel):
    status: str = "completed"


@router.post("/tracing/traces")
def start_trace(body: StartTraceBody, _=require_principal):
    try:
        trace, root_span = get_distributed_tracing_engine().start_trace(
            operation_name=body.operation_name,
            service_name=body.service_name,
            attributes=body.attributes,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e
    return {"trace": trace, "root_span": root_span}


@router.post("/tracing/spans", response_model=TraceSpan)
def start_span(body: StartSpanBody, _=require_principal):
    try:
        return get_distributed_tracing_engine().start_span(
            trace_id=body.trace_id,
            operation_name=body.operation_name,
            service_name=body.service_name,
            parent_span_id=body.parent_span_id,
            attributes=body.attributes,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.post("/tracing/spans/{span_id}/finish", response_model=TraceSpan)
def finish_span(span_id: str, body: FinishSpanBody, _=require_principal):
    try:
        return get_distributed_tracing_engine().finish_span(
            span_id=span_id,
            status=body.status,
            events=body.events,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/tracing/spans/{span_id}", response_model=TraceSpan)
def get_span(span_id: str, _=require_principal):
    try:
        return get_distributed_tracing_engine().get_span(span_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/tracing/spans", response_model=list[TraceSpan])
def list_spans(
    trace_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_distributed_tracing_engine().list_spans(
        trace_id=trace_id, status=status
    )


@router.post("/tracing/spans/{span_id}/events", response_model=TraceSpan)
def add_event(span_id: str, body: AddEventBody, _=require_principal):
    try:
        return get_distributed_tracing_engine().add_event(span_id, body.event)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.post("/tracing/traces/{trace_id}/finish", response_model=TraceContext)
def finish_trace(trace_id: str, body: FinishTraceBody, _=require_principal):
    try:
        return get_distributed_tracing_engine().finish_trace(
            trace_id=trace_id, status=body.status
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/tracing/traces/{trace_id}", response_model=TraceContext)
def get_trace(trace_id: str, _=require_principal):
    try:
        return get_distributed_tracing_engine().get_trace(trace_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/tracing/traces", response_model=list[TraceContext])
def list_traces(
    status: str | None = Query(None),
    _=require_principal,
):
    return get_distributed_tracing_engine().list_traces(status=status)


@router.get("/tracing/traces/{trace_id}/tree")
def get_trace_tree(trace_id: str, _=require_principal):
    try:
        return get_distributed_tracing_engine().get_trace_tree(trace_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.delete("/tracing/spans/{span_id}")
def delete_span(span_id: str, _=require_principal):
    deleted = get_distributed_tracing_engine().delete_span(span_id)
    return {"deleted": deleted}


@router.delete("/tracing/traces/{trace_id}")
def delete_trace(trace_id: str, _=require_principal):
    deleted = get_distributed_tracing_engine().delete_trace(trace_id)
    return {"deleted": deleted}


# ════════════════════ #27 Pipeline Perf ════════════════════

class CreateProfileBody(BaseModel):
    pipeline_id: str
    optimization_type: str
    description: str = ""
    config: dict[str, Any] | None = None
    estimated_improvement_pct: float = 0.0


class RecordBenchmarkBody(BaseModel):
    pipeline_id: str
    before_duration_ms: float
    after_duration_ms: float
    profile_id: str = ""


@router.post("/perf/profiles", response_model=PerfProfile)
def create_profile(body: CreateProfileBody, _=require_principal):
    try:
        return get_pipeline_perf_engine().create_profile(
            pipeline_id=body.pipeline_id,
            optimization_type=body.optimization_type,
            description=body.description,
            config=body.config,
            estimated_improvement_pct=body.estimated_improvement_pct,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/perf/profiles/{profile_id}", response_model=PerfProfile)
def get_profile(profile_id: str, _=require_principal):
    try:
        return get_pipeline_perf_engine().get_profile(profile_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/perf/profiles", response_model=list[PerfProfile])
def list_profiles(
    pipeline_id: str | None = Query(None),
    optimization_type: str | None = Query(None),
    applied_only: bool = Query(False),
    _=require_principal,
):
    return get_pipeline_perf_engine().list_profiles(
        pipeline_id=pipeline_id,
        optimization_type=optimization_type,
        applied_only=applied_only,
    )


@router.put("/perf/profiles/{profile_id}", response_model=PerfProfile)
def update_profile(profile_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_pipeline_perf_engine().update_profile(profile_id, updates)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.post("/perf/profiles/{profile_id}/apply", response_model=PerfProfile)
def apply_profile(profile_id: str, _=require_principal):
    try:
        return get_pipeline_perf_engine().apply_profile(profile_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.delete("/perf/profiles/{profile_id}")
def delete_profile(profile_id: str, _=require_principal):
    deleted = get_pipeline_perf_engine().delete_profile(profile_id)
    return {"deleted": deleted}


@router.post("/perf/benchmarks", response_model=PerfBenchmark)
def record_benchmark(body: RecordBenchmarkBody, _=require_principal):
    try:
        return get_pipeline_perf_engine().record_benchmark(
            pipeline_id=body.pipeline_id,
            before_duration_ms=body.before_duration_ms,
            after_duration_ms=body.after_duration_ms,
            profile_id=body.profile_id,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/perf/benchmarks/{benchmark_id}", response_model=PerfBenchmark)
def get_benchmark(benchmark_id: str, _=require_principal):
    try:
        return get_pipeline_perf_engine().get_benchmark(benchmark_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/perf/benchmarks", response_model=list[PerfBenchmark])
def list_benchmarks(
    pipeline_id: str | None = Query(None),
    _=require_principal,
):
    return get_pipeline_perf_engine().list_benchmarks(pipeline_id=pipeline_id)


@router.delete("/perf/benchmarks/{benchmark_id}")
def delete_benchmark(benchmark_id: str, _=require_principal):
    deleted = get_pipeline_perf_engine().delete_benchmark(benchmark_id)
    return {"deleted": deleted}


# ════════════════════ #30 Geospatial ════════════════════

class AddFeatureBody(BaseModel):
    name: str
    geometry_type: str
    coordinates: list[Any] | None = None
    properties: dict[str, Any] | None = None
    crs: str = "EPSG:4326"


class BboxQueryBody(BaseModel):
    min_x: float
    min_y: float
    max_x: float
    max_y: float


class DistanceQueryBody(BaseModel):
    center_x: float
    center_y: float
    radius: float


class ExportBody(BaseModel):
    feature_ids: list[str] | None = None


@router.post("/geo/features", response_model=GeoFeature)
def add_feature(body: AddFeatureBody, _=require_principal):
    try:
        return get_geospatial_engine().add_feature(
            name=body.name,
            geometry_type=body.geometry_type,
            coordinates=body.coordinates,
            properties=body.properties,
            crs=body.crs,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/geo/features/{feature_id}", response_model=GeoFeature)
def get_feature(feature_id: str, _=require_principal):
    try:
        return get_geospatial_engine().get_feature(feature_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/geo/features", response_model=list[GeoFeature])
def list_features(
    geometry_type: str | None = Query(None),
    _=require_principal,
):
    return get_geospatial_engine().list_features(geometry_type=geometry_type)


@router.put("/geo/features/{feature_id}", response_model=GeoFeature)
def update_feature(feature_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_geospatial_engine().update_feature(feature_id, updates)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.delete("/geo/features/{feature_id}")
def delete_feature(feature_id: str, _=require_principal):
    deleted = get_geospatial_engine().delete_feature(feature_id)
    return {"deleted": deleted}


@router.post("/geo/query/bbox", response_model=GeoQuery)
def query_bbox(body: BboxQueryBody, _=require_principal):
    try:
        return get_geospatial_engine().query_bbox(
            min_x=body.min_x,
            min_y=body.min_y,
            max_x=body.max_x,
            max_y=body.max_y,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.post("/geo/query/distance", response_model=GeoQuery)
def query_distance(body: DistanceQueryBody, _=require_principal):
    try:
        return get_geospatial_engine().query_distance(
            center_x=body.center_x,
            center_y=body.center_y,
            radius=body.radius,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/geo/queries/{query_id}", response_model=GeoQuery)
def get_query(query_id: str, _=require_principal):
    try:
        return get_geospatial_engine().get_query(query_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/geo/queries", response_model=list[GeoQuery])
def list_queries(
    query_type: str | None = Query(None),
    _=require_principal,
):
    return get_geospatial_engine().list_queries(query_type=query_type)


@router.delete("/geo/queries/{query_id}")
def delete_query(query_id: str, _=require_principal):
    deleted = get_geospatial_engine().delete_query(query_id)
    return {"deleted": deleted}


@router.post("/geo/export")
def export_geojson(body: ExportBody, _=require_principal):
    return get_geospatial_engine().export_geojson(feature_ids=body.feature_ids)


# ════════════════════ #31 Map Visualization ════════════════════

class CreateLayerBody(BaseModel):
    name: str
    layer_type: str
    source: str = ""
    style: dict[str, Any] | None = None
    opacity: float = 1.0
    z_index: int = 0


class CreateTemplateBody(BaseModel):
    name: str
    description: str = ""
    layers: list[str] | None = None
    center: list[float] | None = None
    zoom: float = 1.0


class AddLayerToTemplateBody(BaseModel):
    layer_id: str


@router.post("/map/layers", response_model=MapLayer)
def create_layer(body: CreateLayerBody, _=require_principal):
    try:
        return get_map_visualization_engine().create_layer(
            name=body.name,
            layer_type=body.layer_type,
            source=body.source,
            style=body.style,
            opacity=body.opacity,
            z_index=body.z_index,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/map/layers/{layer_id}", response_model=MapLayer)
def get_layer(layer_id: str, _=require_principal):
    try:
        return get_map_visualization_engine().get_layer(layer_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/map/layers", response_model=list[MapLayer])
def list_layers(
    layer_type: str | None = Query(None),
    visible_only: bool = Query(False),
    _=require_principal,
):
    return get_map_visualization_engine().list_layers(
        layer_type=layer_type, visible_only=visible_only
    )


@router.put("/map/layers/{layer_id}", response_model=MapLayer)
def update_layer(layer_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_map_visualization_engine().update_layer(layer_id, updates)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.post("/map/layers/{layer_id}/toggle", response_model=MapLayer)
def toggle_visibility(layer_id: str, _=require_principal):
    try:
        return get_map_visualization_engine().toggle_visibility(layer_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.delete("/map/layers/{layer_id}")
def delete_layer(layer_id: str, _=require_principal):
    deleted = get_map_visualization_engine().delete_layer(layer_id)
    return {"deleted": deleted}


@router.post("/map/templates", response_model=MapTemplate)
def create_template(body: CreateTemplateBody, _=require_principal):
    try:
        return get_map_visualization_engine().create_template(
            name=body.name,
            description=body.description,
            layers=body.layers,
            center=body.center,
            zoom=body.zoom,
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/map/templates/{template_id}", response_model=MapTemplate)
def get_template(template_id: str, _=require_principal):
    try:
        return get_map_visualization_engine().get_template(template_id)
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.get("/map/templates", response_model=list[MapTemplate])
def list_templates(_=require_principal):
    return get_map_visualization_engine().list_templates()


@router.post("/map/templates/{template_id}/layers", response_model=MapTemplate)
def add_layer_to_template(
    template_id: str, body: AddLayerToTemplateBody, _=require_principal
):
    try:
        return get_map_visualization_engine().add_layer_to_template(
            template_id, body.layer_id
        )
    except TracingPerfGeoMapError as e:
        raise _map_err(e) from e


@router.delete("/map/templates/{template_id}")
def delete_template(template_id: str, _=require_principal):
    deleted = get_map_visualization_engine().delete_template(template_id)
    return {"deleted": deleted}
