"""W2-BO · Distributed Tracing / Pipeline Perf / Geospatial / Map Visualization 引擎组（#26 #27 #30 #31）.

本模块提供 W2+ 低优先级批次的 4 个内存态引擎：
    - DistributedTracingEngine   #26 分布式追踪 OpenTelemetry
    - PipelinePerfEngine          #27 管道性能优化
    - GeospatialEngine            #30 地理空间数据框架
    - MapVisualizationEngine      #31 Map 地图可视化

所有引擎均线程安全（threading.Lock），容量上限 200，FIFO 按时间戳淘汰。
"""
from __future__ import annotations

import threading
import time
import uuid
import random
import math
from typing import Any

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class TracingPerfGeoMapError(Exception):
    """Tracing / Perf / Geo / Map 引擎统一错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def error_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


# ════════════════════ #26 Distributed Tracing ════════════════════

class TraceSpan(BaseModel):
    id: str = Field(default_factory=lambda: _uid("span"))
    trace_id: str
    parent_span_id: str = ""
    operation_name: str
    service_name: str
    start_time: float = Field(default_factory=_now_ts)
    end_time: float = 0
    duration_ms: float = 0
    status: str  # active/completed/error
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)


class TraceContext(BaseModel):
    id: str = Field(default_factory=lambda: _uid("trace"))
    trace_id: str
    root_span_id: str
    span_count: int = 0
    service_count: int = 0
    status: str  # active/completed/error
    started_at: float = Field(default_factory=_now_ts)
    completed_at: float = 0


class DistributedTracingEngine:
    """#26 分布式追踪 OpenTelemetry 引擎。"""

    _MAX_SPANS = 200
    _MAX_TRACES = 200
    _VALID_SPAN_STATUS = {"completed", "error"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._spans: dict[str, TraceSpan] = {}
        self._traces: dict[str, TraceContext] = {}

    def _evict_spans(self) -> None:
        if len(self._spans) >= self._MAX_SPANS:
            oldest_id = min(
                self._spans, key=lambda sid: self._spans[sid].start_time
            )
            del self._spans[oldest_id]

    def _evict_traces(self) -> None:
        if len(self._traces) >= self._MAX_TRACES:
            oldest_id = min(
                self._traces, key=lambda tid: self._traces[tid].started_at
            )
            del self._traces[oldest_id]

    def start_trace(
        self,
        operation_name: str,
        service_name: str,
        attributes: dict | None = None,
    ) -> tuple[TraceContext, TraceSpan]:
        if not operation_name:
            raise TracingPerfGeoMapError(
                "INVALID_INPUT", "operation_name 不可为空"
            )
        if not service_name:
            raise TracingPerfGeoMapError(
                "INVALID_INPUT", "service_name 不可为空"
            )
        trace = TraceContext(trace_id=_uid("tid"), root_span_id="", status="active")
        root_span = TraceSpan(
            trace_id=trace.trace_id,
            parent_span_id="",
            operation_name=operation_name,
            service_name=service_name,
            status="active",
            attributes=attributes or {},
        )
        trace.root_span_id = root_span.id
        trace.span_count = 1
        trace.service_count = 1
        with self._lock:
            self._evict_traces()
            self._evict_spans()
            self._traces[trace.id] = trace
            self._spans[root_span.id] = root_span
        return trace, root_span

    def start_span(
        self,
        trace_id: str,
        operation_name: str,
        service_name: str,
        parent_span_id: str = "",
        attributes: dict | None = None,
    ) -> TraceSpan:
        if not operation_name:
            raise TracingPerfGeoMapError(
                "INVALID_INPUT", "operation_name 不可为空"
            )
        if not service_name:
            raise TracingPerfGeoMapError(
                "INVALID_INPUT", "service_name 不可为空"
            )
        span = TraceSpan(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service_name=service_name,
            status="active",
            attributes=attributes or {},
        )
        with self._lock:
            # 定位所属 trace（按 trace_id 匹配）
            matched: TraceContext | None = None
            for t in self._traces.values():
                if t.trace_id == trace_id:
                    matched = t
                    break
            if matched is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"trace {trace_id} not found"
                )
            self._evict_spans()
            self._spans[span.id] = span
            updated = matched.model_copy(
                update={"span_count": matched.span_count + 1}
            )
            self._traces[matched.id] = updated
        return span

    def finish_span(
        self,
        span_id: str,
        status: str = "completed",
        events: list[dict] | None = None,
    ) -> TraceSpan:
        if status not in self._VALID_SPAN_STATUS:
            raise TracingPerfGeoMapError(
                "INVALID_STATUS",
                f"status must be one of {sorted(self._VALID_SPAN_STATUS)}",
            )
        with self._lock:
            span = self._spans.get(span_id)
            if span is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"span {span_id} not found"
                )
            end_time = _now_ts()
            duration_ms = (end_time - span.start_time) * 1000
            updated = span.model_copy(
                update={
                    "end_time": end_time,
                    "duration_ms": duration_ms,
                    "status": status,
                    "events": list(span.events) + (events or []),
                }
            )
            self._spans[span_id] = updated
        return updated

    def get_span(self, span_id: str) -> TraceSpan:
        with self._lock:
            span = self._spans.get(span_id)
        if span is None:
            raise TracingPerfGeoMapError("NOT_FOUND", f"span {span_id} not found")
        return span

    def list_spans(
        self,
        trace_id: str | None = None,
        status: str | None = None,
    ) -> list[TraceSpan]:
        with self._lock:
            results = list(self._spans.values())
        if trace_id is not None:
            results = [s for s in results if s.trace_id == trace_id]
        if status is not None:
            results = [s for s in results if s.status == status]
        return sorted(results, key=lambda s: s.start_time)

    def add_event(self, span_id: str, event: dict[str, Any]) -> TraceSpan:
        with self._lock:
            span = self._spans.get(span_id)
            if span is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"span {span_id} not found"
                )
            updated = span.model_copy(
                update={"events": list(span.events) + [event]}
            )
            self._spans[span_id] = updated
        return updated

    def finish_trace(self, trace_id: str, status: str = "completed") -> TraceContext:
        if status not in self._VALID_SPAN_STATUS:
            raise TracingPerfGeoMapError(
                "INVALID_STATUS",
                f"status must be one of {sorted(self._VALID_SPAN_STATUS)}",
            )
        with self._lock:
            matched: TraceContext | None = None
            for t in self._traces.values():
                if t.trace_id == trace_id:
                    matched = t
                    break
            if matched is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"trace {trace_id} not found"
                )
            updated = matched.model_copy(
                update={
                    "completed_at": _now_ts(),
                    "status": status,
                }
            )
            self._traces[matched.id] = updated
        return updated

    def get_trace(self, trace_id: str) -> TraceContext:
        with self._lock:
            matched: TraceContext | None = None
            for t in self._traces.values():
                if t.trace_id == trace_id:
                    matched = t
                    break
        if matched is None:
            raise TracingPerfGeoMapError("NOT_FOUND", f"trace {trace_id} not found")
        return matched

    def list_traces(self, status: str | None = None) -> list[TraceContext]:
        with self._lock:
            results = list(self._traces.values())
        if status is not None:
            results = [t for t in results if t.status == status]
        return sorted(results, key=lambda t: t.started_at)

    def get_trace_tree(self, trace_id: str) -> dict[str, Any]:
        with self._lock:
            matched: TraceContext | None = None
            for t in self._traces.values():
                if t.trace_id == trace_id:
                    matched = t
                    break
            if matched is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"trace {trace_id} not found"
                )
            spans = [s for s in self._spans.values() if s.trace_id == trace_id]
        spans_sorted = sorted(spans, key=lambda s: s.start_time)
        total_duration_ms = sum(s.duration_ms for s in spans_sorted if s.duration_ms > 0)
        by_service: dict[str, int] = {}
        for s in spans_sorted:
            by_service[s.service_name] = by_service.get(s.service_name, 0) + 1
        return {
            "trace_id": trace_id,
            "spans": [s.model_dump() for s in spans_sorted],
            "total_duration_ms": total_duration_ms,
            "by_service": by_service,
        }

    def delete_span(self, span_id: str) -> bool:
        with self._lock:
            return self._spans.pop(span_id, None) is not None

    def delete_trace(self, trace_id: str) -> bool:
        with self._lock:
            matched_id: str | None = None
            for tid, t in self._traces.items():
                if t.trace_id == trace_id:
                    matched_id = tid
                    break
            if matched_id is None:
                return False
            del self._traces[matched_id]
            # 同步清理该 trace 下的 spans
            for sid in [s.id for s in self._spans.values() if s.trace_id == trace_id]:
                self._spans.pop(sid, None)
            return True


# ════════════════════ #27 Pipeline Perf ════════════════════

class PerfProfile(BaseModel):
    id: str = Field(default_factory=lambda: _uid("perf"))
    pipeline_id: str
    optimization_type: str  # spark_optimization/projection_pushdown/native_acceleration/profile_tuning
    description: str
    config: dict[str, Any] = Field(default_factory=dict)
    estimated_improvement_pct: float = 0.0
    applied: bool = False
    created_at: float = Field(default_factory=_now_ts)


class PerfBenchmark(BaseModel):
    id: str = Field(default_factory=lambda: _uid("bench"))
    pipeline_id: str
    profile_id: str = ""
    before_duration_ms: float = 0
    after_duration_ms: float = 0
    improvement_pct: float = 0.0
    measured_at: float = Field(default_factory=_now_ts)


class PipelinePerfEngine:
    """#27 管道性能优化引擎。"""

    _MAX_PROFILES = 200
    _MAX_BENCHMARKS = 200
    _VALID_OPT_TYPES = {
        "spark_optimization",
        "projection_pushdown",
        "native_acceleration",
        "profile_tuning",
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: dict[str, PerfProfile] = {}
        self._benchmarks: dict[str, PerfBenchmark] = {}

    def _evict_profiles(self) -> None:
        if len(self._profiles) >= self._MAX_PROFILES:
            oldest_id = min(
                self._profiles, key=lambda pid: self._profiles[pid].created_at
            )
            del self._profiles[oldest_id]

    def _evict_benchmarks(self) -> None:
        if len(self._benchmarks) >= self._MAX_BENCHMARKS:
            oldest_id = min(
                self._benchmarks,
                key=lambda bid: self._benchmarks[bid].measured_at,
            )
            del self._benchmarks[oldest_id]

    def create_profile(
        self,
        pipeline_id: str,
        optimization_type: str,
        description: str = "",
        config: dict | None = None,
        estimated_improvement_pct: float = 0.0,
    ) -> PerfProfile:
        if not pipeline_id:
            raise TracingPerfGeoMapError(
                "INVALID_INPUT", "pipeline_id 不可为空"
            )
        if optimization_type not in self._VALID_OPT_TYPES:
            raise TracingPerfGeoMapError(
                "INVALID_OPTIMIZATION_TYPE",
                f"optimization_type must be one of {sorted(self._VALID_OPT_TYPES)}",
            )
        profile = PerfProfile(
            pipeline_id=pipeline_id,
            optimization_type=optimization_type,
            description=description,
            config=config or {},
            estimated_improvement_pct=estimated_improvement_pct,
        )
        with self._lock:
            self._evict_profiles()
            self._profiles[profile.id] = profile
        return profile

    def get_profile(self, profile_id: str) -> PerfProfile:
        with self._lock:
            profile = self._profiles.get(profile_id)
        if profile is None:
            raise TracingPerfGeoMapError(
                "NOT_FOUND", f"profile {profile_id} not found"
            )
        return profile

    def list_profiles(
        self,
        pipeline_id: str | None = None,
        optimization_type: str | None = None,
        applied_only: bool = False,
    ) -> list[PerfProfile]:
        with self._lock:
            results = list(self._profiles.values())
        if pipeline_id is not None:
            results = [p for p in results if p.pipeline_id == pipeline_id]
        if optimization_type is not None:
            results = [p for p in results if p.optimization_type == optimization_type]
        if applied_only:
            results = [p for p in results if p.applied]
        return sorted(results, key=lambda p: p.created_at)

    def update_profile(self, profile_id: str, updates: dict[str, Any]) -> PerfProfile:
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"profile {profile_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(profile).model_fields
            }
            updated = profile.model_copy(update=applicable)
            self._profiles[profile_id] = updated
        return updated

    def apply_profile(self, profile_id: str) -> PerfProfile:
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"profile {profile_id} not found"
                )
            updated = profile.model_copy(update={"applied": True})
            self._profiles[profile_id] = updated
        return updated

    def delete_profile(self, profile_id: str) -> bool:
        with self._lock:
            return self._profiles.pop(profile_id, None) is not None

    def record_benchmark(
        self,
        pipeline_id: str,
        before_duration_ms: float,
        after_duration_ms: float,
        profile_id: str = "",
    ) -> PerfBenchmark:
        if not pipeline_id:
            raise TracingPerfGeoMapError(
                "INVALID_INPUT", "pipeline_id 不可为空"
            )
        if before_duration_ms <= 0:
            raise TracingPerfGeoMapError(
                "INVALID_DURATION", "before_duration_ms must be > 0"
            )
        improvement_pct = (before_duration_ms - after_duration_ms) / before_duration_ms * 100
        benchmark = PerfBenchmark(
            pipeline_id=pipeline_id,
            profile_id=profile_id,
            before_duration_ms=before_duration_ms,
            after_duration_ms=after_duration_ms,
            improvement_pct=improvement_pct,
        )
        with self._lock:
            self._evict_benchmarks()
            self._benchmarks[benchmark.id] = benchmark
        return benchmark

    def get_benchmark(self, benchmark_id: str) -> PerfBenchmark:
        with self._lock:
            benchmark = self._benchmarks.get(benchmark_id)
        if benchmark is None:
            raise TracingPerfGeoMapError(
                "NOT_FOUND", f"benchmark {benchmark_id} not found"
            )
        return benchmark

    def list_benchmarks(self, pipeline_id: str | None = None) -> list[PerfBenchmark]:
        with self._lock:
            results = list(self._benchmarks.values())
        if pipeline_id is not None:
            results = [b for b in results if b.pipeline_id == pipeline_id]
        return sorted(results, key=lambda b: b.measured_at)

    def delete_benchmark(self, benchmark_id: str) -> bool:
        with self._lock:
            return self._benchmarks.pop(benchmark_id, None) is not None


# ════════════════════ #30 Geospatial ════════════════════

class GeoFeature(BaseModel):
    id: str = Field(default_factory=lambda: _uid("geo"))
    name: str
    geometry_type: str  # point/linestring/polygon/multipoint/multilinestring/multipolygon
    coordinates: list[Any] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    crs: str = "EPSG:4326"
    created_at: float = Field(default_factory=_now_ts)


class GeoQuery(BaseModel):
    id: str = Field(default_factory=lambda: _uid("gq"))
    query_type: str  # bbox/distance/within/intersect
    parameters: dict[str, Any] = Field(default_factory=dict)
    results: list[str] = Field(default_factory=list)
    executed_at: float = Field(default_factory=_now_ts)


class GeospatialEngine:
    """#30 地理空间数据框架引擎。"""

    _MAX_FEATURES = 200
    _MAX_QUERIES = 200
    _VALID_GEOMETRY_TYPES = {
        "point",
        "linestring",
        "polygon",
        "multipoint",
        "multilinestring",
        "multipolygon",
    }
    _VALID_QUERY_TYPES = {"bbox", "distance", "within", "intersect"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._features: dict[str, GeoFeature] = {}
        self._queries: dict[str, GeoQuery] = {}

    def _evict_features(self) -> None:
        if len(self._features) >= self._MAX_FEATURES:
            oldest_id = min(
                self._features, key=lambda fid: self._features[fid].created_at
            )
            del self._features[oldest_id]

    def _evict_queries(self) -> None:
        if len(self._queries) >= self._MAX_QUERIES:
            oldest_id = min(
                self._queries, key=lambda qid: self._queries[qid].executed_at
            )
            del self._queries[oldest_id]

    @staticmethod
    def _point_xy(coords: list[Any]) -> tuple[float, float] | None:
        if len(coords) >= 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
            return float(coords[0]), float(coords[1])
        return None

    def add_feature(
        self,
        name: str,
        geometry_type: str,
        coordinates: list | None = None,
        properties: dict | None = None,
        crs: str = "EPSG:4326",
    ) -> GeoFeature:
        if not name:
            raise TracingPerfGeoMapError("INVALID_INPUT", "name 不可为空")
        if geometry_type not in self._VALID_GEOMETRY_TYPES:
            raise TracingPerfGeoMapError(
                "INVALID_GEOMETRY_TYPE",
                f"geometry_type must be one of {sorted(self._VALID_GEOMETRY_TYPES)}",
            )
        feature = GeoFeature(
            name=name,
            geometry_type=geometry_type,
            coordinates=coordinates or [],
            properties=properties or {},
            crs=crs,
        )
        with self._lock:
            self._evict_features()
            self._features[feature.id] = feature
        return feature

    def get_feature(self, feature_id: str) -> GeoFeature:
        with self._lock:
            feature = self._features.get(feature_id)
        if feature is None:
            raise TracingPerfGeoMapError(
                "NOT_FOUND", f"feature {feature_id} not found"
            )
        return feature

    def list_features(self, geometry_type: str | None = None) -> list[GeoFeature]:
        with self._lock:
            results = list(self._features.values())
        if geometry_type is not None:
            results = [f for f in results if f.geometry_type == geometry_type]
        return sorted(results, key=lambda f: f.created_at)

    def update_feature(self, feature_id: str, updates: dict[str, Any]) -> GeoFeature:
        with self._lock:
            feature = self._features.get(feature_id)
            if feature is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"feature {feature_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(feature).model_fields
            }
            updated = feature.model_copy(update=applicable)
            self._features[feature_id] = updated
        return updated

    def delete_feature(self, feature_id: str) -> bool:
        with self._lock:
            return self._features.pop(feature_id, None) is not None

    def query_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
    ) -> GeoQuery:
        with self._lock:
            features = list(self._features.values())
        matched: list[str] = []
        for f in features:
            xy = self._point_xy(f.coordinates)
            if xy is None:
                continue
            x, y = xy
            if min_x <= x <= max_x and min_y <= y <= max_y:
                matched.append(f.id)
        query = GeoQuery(
            query_type="bbox",
            parameters={
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
            },
            results=matched,
        )
        with self._lock:
            self._evict_queries()
            self._queries[query.id] = query
        return query

    def query_distance(
        self,
        center_x: float,
        center_y: float,
        radius: float,
    ) -> GeoQuery:
        if radius < 0:
            raise TracingPerfGeoMapError(
                "INVALID_RADIUS", "radius must be >= 0"
            )
        with self._lock:
            features = list(self._features.values())
        matched: list[str] = []
        for f in features:
            xy = self._point_xy(f.coordinates)
            if xy is None:
                continue
            x, y = xy
            dist = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            if dist <= radius:
                matched.append(f.id)
        query = GeoQuery(
            query_type="distance",
            parameters={
                "center_x": center_x,
                "center_y": center_y,
                "radius": radius,
            },
            results=matched,
        )
        with self._lock:
            self._evict_queries()
            self._queries[query.id] = query
        return query

    def get_query(self, query_id: str) -> GeoQuery:
        with self._lock:
            query = self._queries.get(query_id)
        if query is None:
            raise TracingPerfGeoMapError(
                "NOT_FOUND", f"query {query_id} not found"
            )
        return query

    def list_queries(self, query_type: str | None = None) -> list[GeoQuery]:
        with self._lock:
            results = list(self._queries.values())
        if query_type is not None:
            results = [q for q in results if q.query_type == query_type]
        return sorted(results, key=lambda q: q.executed_at)

    def delete_query(self, query_id: str) -> bool:
        with self._lock:
            return self._queries.pop(query_id, None) is not None

    def export_geojson(self, feature_ids: list[str] | None = None) -> dict[str, Any]:
        with self._lock:
            if feature_ids is None:
                features = list(self._features.values())
            else:
                features = [
                    self._features[fid]
                    for fid in feature_ids
                    if fid in self._features
                ]
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": f.id,
                    "geometry": {
                        "type": f.geometry_type,
                        "coordinates": f.coordinates,
                    },
                    "properties": {
                        "name": f.name,
                        "crs": f.crs,
                        **f.properties,
                    },
                }
                for f in features
            ],
        }


# ════════════════════ #31 Map Visualization ════════════════════

class MapLayer(BaseModel):
    id: str = Field(default_factory=lambda: _uid("layer"))
    name: str
    layer_type: str  # tile/vector/geojson/heat/cluster
    source: str = ""
    style: dict[str, Any] = Field(default_factory=dict)
    visible: bool = True
    opacity: float = 1.0
    z_index: int = 0
    created_at: float = Field(default_factory=_now_ts)


class MapTemplate(BaseModel):
    id: str = Field(default_factory=lambda: _uid("map"))
    name: str
    description: str
    layers: list[str] = Field(default_factory=list)
    center: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    zoom: float = 1.0
    created_at: float = Field(default_factory=_now_ts)


class MapVisualizationEngine:
    """#31 Map 地图可视化引擎。"""

    _MAX_LAYERS = 200
    _MAX_TEMPLATES = 200
    _VALID_LAYER_TYPES = {"tile", "vector", "geojson", "heat", "cluster"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._layers: dict[str, MapLayer] = {}
        self._templates: dict[str, MapTemplate] = {}

    def _evict_layers(self) -> None:
        if len(self._layers) >= self._MAX_LAYERS:
            oldest_id = min(
                self._layers, key=lambda lid: self._layers[lid].created_at
            )
            del self._layers[oldest_id]

    def _evict_templates(self) -> None:
        if len(self._templates) >= self._MAX_TEMPLATES:
            oldest_id = min(
                self._templates, key=lambda tid: self._templates[tid].created_at
            )
            del self._templates[oldest_id]

    def create_layer(
        self,
        name: str,
        layer_type: str,
        source: str = "",
        style: dict | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> MapLayer:
        if not name:
            raise TracingPerfGeoMapError("INVALID_INPUT", "name 不可为空")
        if layer_type not in self._VALID_LAYER_TYPES:
            raise TracingPerfGeoMapError(
                "INVALID_LAYER_TYPE",
                f"layer_type must be one of {sorted(self._VALID_LAYER_TYPES)}",
            )
        if opacity < 0 or opacity > 1:
            raise TracingPerfGeoMapError(
                "INVALID_OPACITY", "opacity must be in [0, 1]"
            )
        layer = MapLayer(
            name=name,
            layer_type=layer_type,
            source=source,
            style=style or {},
            opacity=opacity,
            z_index=z_index,
        )
        with self._lock:
            self._evict_layers()
            self._layers[layer.id] = layer
        return layer

    def get_layer(self, layer_id: str) -> MapLayer:
        with self._lock:
            layer = self._layers.get(layer_id)
        if layer is None:
            raise TracingPerfGeoMapError(
                "NOT_FOUND", f"layer {layer_id} not found"
            )
        return layer

    def list_layers(
        self,
        layer_type: str | None = None,
        visible_only: bool = False,
    ) -> list[MapLayer]:
        with self._lock:
            results = list(self._layers.values())
        if layer_type is not None:
            results = [l for l in results if l.layer_type == layer_type]
        if visible_only:
            results = [l for l in results if l.visible]
        return sorted(results, key=lambda l: l.created_at)

    def update_layer(self, layer_id: str, updates: dict[str, Any]) -> MapLayer:
        with self._lock:
            layer = self._layers.get(layer_id)
            if layer is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"layer {layer_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(layer).model_fields
            }
            updated = layer.model_copy(update=applicable)
            self._layers[layer_id] = updated
        return updated

    def toggle_visibility(self, layer_id: str) -> MapLayer:
        with self._lock:
            layer = self._layers.get(layer_id)
            if layer is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"layer {layer_id} not found"
                )
            updated = layer.model_copy(update={"visible": not layer.visible})
            self._layers[layer_id] = updated
        return updated

    def delete_layer(self, layer_id: str) -> bool:
        with self._lock:
            return self._layers.pop(layer_id, None) is not None

    def create_template(
        self,
        name: str,
        description: str = "",
        layers: list[str] | None = None,
        center: list[float] | None = None,
        zoom: float = 1.0,
    ) -> MapTemplate:
        if not name:
            raise TracingPerfGeoMapError("INVALID_INPUT", "name 不可为空")
        template = MapTemplate(
            name=name,
            description=description,
            layers=layers or [],
            center=center if center is not None else [0.0, 0.0],
            zoom=zoom,
        )
        with self._lock:
            self._evict_templates()
            self._templates[template.id] = template
        return template

    def get_template(self, template_id: str) -> MapTemplate:
        with self._lock:
            template = self._templates.get(template_id)
        if template is None:
            raise TracingPerfGeoMapError(
                "NOT_FOUND", f"template {template_id} not found"
            )
        return template

    def list_templates(self) -> list[MapTemplate]:
        with self._lock:
            results = list(self._templates.values())
        return sorted(results, key=lambda t: t.created_at)

    def add_layer_to_template(self, template_id: str, layer_id: str) -> MapTemplate:
        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                raise TracingPerfGeoMapError(
                    "NOT_FOUND", f"template {template_id} not found"
                )
            layers = list(template.layers)
            if layer_id not in layers:
                layers.append(layer_id)
            updated = template.model_copy(update={"layers": layers})
            self._templates[template_id] = updated
        return updated

    def delete_template(self, template_id: str) -> bool:
        with self._lock:
            return self._templates.pop(template_id, None) is not None


# ────────────────────────────────────────────────────────────────
# 单例 getter（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_tracing_engine: DistributedTracingEngine | None = None
_perf_engine: PipelinePerfEngine | None = None
_geo_engine: GeospatialEngine | None = None
_map_engine: MapVisualizationEngine | None = None


def get_distributed_tracing_engine() -> DistributedTracingEngine:
    global _tracing_engine
    if _tracing_engine is None:
        with _lock:
            if _tracing_engine is None:
                _tracing_engine = DistributedTracingEngine()
    return _tracing_engine


def get_pipeline_perf_engine() -> PipelinePerfEngine:
    global _perf_engine
    if _perf_engine is None:
        with _lock:
            if _perf_engine is None:
                _perf_engine = PipelinePerfEngine()
    return _perf_engine


def get_geospatial_engine() -> GeospatialEngine:
    global _geo_engine
    if _geo_engine is None:
        with _lock:
            if _geo_engine is None:
                _geo_engine = GeospatialEngine()
    return _geo_engine


def get_map_visualization_engine() -> MapVisualizationEngine:
    global _map_engine
    if _map_engine is None:
        with _lock:
            if _map_engine is None:
                _map_engine = MapVisualizationEngine()
    return _map_engine
