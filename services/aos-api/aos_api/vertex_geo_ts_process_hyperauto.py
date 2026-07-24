"""W2-BP · Vertex 数字孪生 / 地理时间序列 / Process Mining / Hyperauto 引擎组（#32 #33 #34 #35）.

本模块提供 W2+ 低优先级批次（最终批）的 4 个内存态引擎：
    - DigitalTwinEngine        #32 Vertex 数字孪生
    - GeoTimeSeriesEngine      #33 地理时间序列
    - ProcessMiningEngine      #34 Process Mining
    - HyperautoEngine          #35 Hyperauto 开箱集成

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


class VertexGeoTsProcessError(Exception):
    """Vertex / Geo TS / Process / Hyperauto 引擎统一错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def error_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


# ════════════════════ #32 Digital Twin ════════════════════

class TwinModel(BaseModel):
    id: str = Field(default_factory=lambda: _uid("twin"))
    name: str
    description: str
    physical_entity_id: str
    state: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=_now_ts)


class TwinSimulation(BaseModel):
    id: str = Field(default_factory=lambda: _uid("sim"))
    twin_id: str
    steps: int = 10
    results: list[dict[str, Any]] = Field(default_factory=list)
    status: str  # pending/running/completed/failed
    started_at: float = Field(default_factory=_now_ts)
    completed_at: float = 0


class CausalAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: _uid("causal"))
    twin_id: str
    cause_variable: str
    effect_variable: str
    correlation: float = 0.0
    lag_seconds: int = 0
    description: str = ""
    created_at: float = Field(default_factory=_now_ts)


class DigitalTwinEngine:
    """#32 Vertex 数字孪生引擎。"""

    _MAX_TWINS = 200
    _MAX_SIMULATIONS = 200
    _MAX_CAUSAL = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._twins: dict[str, TwinModel] = {}
        self._simulations: dict[str, TwinSimulation] = {}
        self._causal: dict[str, CausalAnalysis] = {}

    def _evict_twins(self) -> None:
        if len(self._twins) >= self._MAX_TWINS:
            oldest_id = min(
                self._twins, key=lambda tid: self._twins[tid].created_at
            )
            del self._twins[oldest_id]

    def _evict_simulations(self) -> None:
        if len(self._simulations) >= self._MAX_SIMULATIONS:
            oldest_id = min(
                self._simulations,
                key=lambda sid: self._simulations[sid].started_at,
            )
            del self._simulations[oldest_id]

    def _evict_causal(self) -> None:
        if len(self._causal) >= self._MAX_CAUSAL:
            oldest_id = min(
                self._causal, key=lambda aid: self._causal[aid].created_at
            )
            del self._causal[oldest_id]

    def create_twin(
        self,
        name: str,
        description: str = "",
        physical_entity_id: str = "",
        state: dict | None = None,
        parameters: dict | None = None,
    ) -> TwinModel:
        if not name:
            raise VertexGeoTsProcessError("INVALID_INPUT", "name 不可为空")
        twin = TwinModel(
            name=name,
            description=description,
            physical_entity_id=physical_entity_id,
            state=state or {},
            parameters=parameters or {},
        )
        with self._lock:
            self._evict_twins()
            self._twins[twin.id] = twin
        return twin

    def get_twin(self, twin_id: str) -> TwinModel:
        with self._lock:
            twin = self._twins.get(twin_id)
        if twin is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"twin {twin_id} not found"
            )
        return twin

    def list_twins(self) -> list[TwinModel]:
        with self._lock:
            results = list(self._twins.values())
        return sorted(results, key=lambda t: t.created_at)

    def update_twin(self, twin_id: str, updates: dict[str, Any]) -> TwinModel:
        with self._lock:
            twin = self._twins.get(twin_id)
            if twin is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"twin {twin_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(twin).model_fields
            }
            updated = twin.model_copy(update=applicable)
            self._twins[twin_id] = updated
        return updated

    def delete_twin(self, twin_id: str) -> bool:
        with self._lock:
            return self._twins.pop(twin_id, None) is not None

    def run_simulation(
        self, twin_id: str, steps: int = 10
    ) -> TwinSimulation:
        with self._lock:
            twin = self._twins.get(twin_id)
            if twin is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"twin {twin_id} not found"
                )
            twin_params = dict(twin.parameters)
        sim = TwinSimulation(
            twin_id=twin_id,
            steps=steps,
            status="running",
        )
        param_keys = list(twin_params.keys()) or ["value"]
        results: list[dict[str, Any]] = []
        for step in range(steps):
            state_values = {
                key: random.random() * 100 for key in param_keys
            }
            results.append({"step": step, "state": state_values})
        sim.results = results
        sim.status = "completed"
        sim.completed_at = _now_ts()
        with self._lock:
            self._evict_simulations()
            self._simulations[sim.id] = sim
        return sim

    def get_simulation(self, simulation_id: str) -> TwinSimulation:
        with self._lock:
            sim = self._simulations.get(simulation_id)
        if sim is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"simulation {simulation_id} not found"
            )
        return sim

    def list_simulations(
        self,
        twin_id: str | None = None,
        status: str | None = None,
    ) -> list[TwinSimulation]:
        with self._lock:
            results = list(self._simulations.values())
        if twin_id is not None:
            results = [s for s in results if s.twin_id == twin_id]
        if status is not None:
            results = [s for s in results if s.status == status]
        return sorted(results, key=lambda s: s.started_at)

    def delete_simulation(self, simulation_id: str) -> bool:
        with self._lock:
            return self._simulations.pop(simulation_id, None) is not None

    def analyze_causality(
        self,
        twin_id: str,
        cause_variable: str,
        effect_variable: str,
        correlation: float = 0.0,
        lag_seconds: int = 0,
        description: str = "",
    ) -> CausalAnalysis:
        with self._lock:
            twin = self._twins.get(twin_id)
            if twin is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"twin {twin_id} not found"
                )
        if correlation < -1 or correlation > 1:
            raise VertexGeoTsProcessError(
                "INVALID_CORRELATION", "correlation must be in [-1, 1]"
            )
        if not cause_variable:
            raise VertexGeoTsProcessError(
                "INVALID_INPUT", "cause_variable 不可为空"
            )
        if not effect_variable:
            raise VertexGeoTsProcessError(
                "INVALID_INPUT", "effect_variable 不可为空"
            )
        analysis = CausalAnalysis(
            twin_id=twin_id,
            cause_variable=cause_variable,
            effect_variable=effect_variable,
            correlation=correlation,
            lag_seconds=lag_seconds,
            description=description,
        )
        with self._lock:
            self._evict_causal()
            self._causal[analysis.id] = analysis
        return analysis

    def get_causal_analysis(self, analysis_id: str) -> CausalAnalysis:
        with self._lock:
            analysis = self._causal.get(analysis_id)
        if analysis is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"causal analysis {analysis_id} not found"
            )
        return analysis

    def list_causal_analyses(
        self, twin_id: str | None = None
    ) -> list[CausalAnalysis]:
        with self._lock:
            results = list(self._causal.values())
        if twin_id is not None:
            results = [a for a in results if a.twin_id == twin_id]
        return sorted(results, key=lambda a: a.created_at)

    def delete_causal_analysis(self, analysis_id: str) -> bool:
        with self._lock:
            return self._causal.pop(analysis_id, None) is not None


# ════════════════════ #33 Geo Time Series ════════════════════

class LocationTrack(BaseModel):
    id: str = Field(default_factory=lambda: _uid("track"))
    entity_id: str
    name: str
    sync_enabled: bool = True
    last_position: dict[str, float] = Field(default_factory=dict)
    last_timestamp: float = 0
    point_count: int = 0
    created_at: float = Field(default_factory=_now_ts)


class LocationPoint(BaseModel):
    id: str = Field(default_factory=lambda: _uid("pt"))
    track_id: str
    latitude: float
    longitude: float
    elevation: float = 0.0
    speed: float = 0.0
    heading: float = 0.0
    timestamp: float = Field(default_factory=_now_ts)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeoTimeSeriesEngine:
    """#33 地理时间序列引擎。"""

    _MAX_TRACKS = 200
    _MAX_POINTS = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tracks: dict[str, LocationTrack] = {}
        self._points: dict[str, LocationPoint] = {}

    def _evict_tracks(self) -> None:
        if len(self._tracks) >= self._MAX_TRACKS:
            oldest_id = min(
                self._tracks, key=lambda tid: self._tracks[tid].created_at
            )
            del self._tracks[oldest_id]

    def _evict_points(self) -> None:
        if len(self._points) >= self._MAX_POINTS:
            oldest_id = min(
                self._points,
                key=lambda pid: self._points[pid].timestamp,
            )
            del self._points[oldest_id]

    @staticmethod
    def _haversine_km(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        radius_km = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return 2 * radius_km * math.asin(math.sqrt(a))

    def create_track(
        self,
        entity_id: str,
        name: str,
        sync_enabled: bool = True,
    ) -> LocationTrack:
        if not entity_id:
            raise VertexGeoTsProcessError(
                "INVALID_INPUT", "entity_id 不可为空"
            )
        if not name:
            raise VertexGeoTsProcessError("INVALID_INPUT", "name 不可为空")
        track = LocationTrack(
            entity_id=entity_id,
            name=name,
            sync_enabled=sync_enabled,
        )
        with self._lock:
            self._evict_tracks()
            self._tracks[track.id] = track
        return track

    def get_track(self, track_id: str) -> LocationTrack:
        with self._lock:
            track = self._tracks.get(track_id)
        if track is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"track {track_id} not found"
            )
        return track

    def list_tracks(
        self,
        entity_id: str | None = None,
        sync_enabled_only: bool = False,
    ) -> list[LocationTrack]:
        with self._lock:
            results = list(self._tracks.values())
        if entity_id is not None:
            results = [t for t in results if t.entity_id == entity_id]
        if sync_enabled_only:
            results = [t for t in results if t.sync_enabled]
        return sorted(results, key=lambda t: t.created_at)

    def update_track(
        self, track_id: str, updates: dict[str, Any]
    ) -> LocationTrack:
        with self._lock:
            track = self._tracks.get(track_id)
            if track is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"track {track_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(track).model_fields
            }
            updated = track.model_copy(update=applicable)
            self._tracks[track_id] = updated
        return updated

    def delete_track(self, track_id: str) -> bool:
        with self._lock:
            existed = self._tracks.pop(track_id, None) is not None
            if existed:
                # 同步清理该 track 下的 points
                for pid in [
                    p.id for p in self._points.values() if p.track_id == track_id
                ]:
                    self._points.pop(pid, None)
            return existed

    def record_point(
        self,
        track_id: str,
        latitude: float,
        longitude: float,
        elevation: float = 0,
        speed: float = 0,
        heading: float = 0,
        metadata: dict | None = None,
    ) -> LocationPoint:
        if latitude < -90 or latitude > 90:
            raise VertexGeoTsProcessError(
                "INVALID_LATITUDE", "latitude must be in [-90, 90]"
            )
        if longitude < -180 or longitude > 180:
            raise VertexGeoTsProcessError(
                "INVALID_LONGITUDE", "longitude must be in [-180, 180]"
            )
        point = LocationPoint(
            track_id=track_id,
            latitude=latitude,
            longitude=longitude,
            elevation=elevation,
            speed=speed,
            heading=heading,
            metadata=metadata or {},
        )
        with self._lock:
            track = self._tracks.get(track_id)
            if track is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"track {track_id} not found"
                )
            self._evict_points()
            self._points[point.id] = point
            count = sum(
                1 for p in self._points.values() if p.track_id == track_id
            )
            updated = track.model_copy(
                update={
                    "last_position": {
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    "last_timestamp": point.timestamp,
                    "point_count": count,
                }
            )
            self._tracks[track_id] = updated
        return point

    def get_point(self, point_id: str) -> LocationPoint:
        with self._lock:
            point = self._points.get(point_id)
        if point is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"point {point_id} not found"
            )
        return point

    def list_points(
        self,
        track_id: str | None = None,
        limit: int = 100,
    ) -> list[LocationPoint]:
        with self._lock:
            results = list(self._points.values())
        if track_id is not None:
            results = [p for p in results if p.track_id == track_id]
        results.sort(key=lambda p: p.timestamp, reverse=True)
        return results[:limit]

    def get_track_path(
        self, track_id: str, limit: int = 100
    ) -> dict[str, Any]:
        with self._lock:
            track = self._tracks.get(track_id)
            if track is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"track {track_id} not found"
                )
            points = [
                p for p in self._points.values() if p.track_id == track_id
            ]
        points.sort(key=lambda p: p.timestamp)
        points = points[:limit]
        distance_km = 0.0
        for i in range(1, len(points)):
            distance_km += self._haversine_km(
                points[i - 1].latitude,
                points[i - 1].longitude,
                points[i].latitude,
                points[i].longitude,
            )
        return {
            "track_id": track_id,
            "points": [p.model_dump() for p in points],
            "total_points": len(points),
            "distance_km": distance_km,
        }

    def delete_point(self, point_id: str) -> bool:
        with self._lock:
            return self._points.pop(point_id, None) is not None


# ════════════════════ #34 Process Mining ════════════════════

class EventLog(BaseModel):
    id: str = Field(default_factory=lambda: _uid("elog"))
    case_id: str
    activity: str
    timestamp: float = Field(default_factory=_now_ts)
    resource: str = ""
    cost: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessFlow(BaseModel):
    id: str = Field(default_factory=lambda: _uid("flow"))
    name: str
    activities: list[str] = Field(default_factory=list)
    transitions: list[dict[str, Any]] = Field(default_factory=list)
    bottlenecks: list[dict[str, Any]] = Field(default_factory=list)
    case_count: int = 0
    created_at: float = Field(default_factory=_now_ts)


class ProcessMiningEngine:
    """#34 Process Mining 引擎。"""

    _MAX_LOGS = 200
    _MAX_FLOWS = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._logs: dict[str, EventLog] = {}
        self._flows: dict[str, ProcessFlow] = {}

    def _evict_logs(self) -> None:
        if len(self._logs) >= self._MAX_LOGS:
            oldest_id = min(
                self._logs, key=lambda eid: self._logs[eid].timestamp
            )
            del self._logs[oldest_id]

    def _evict_flows(self) -> None:
        if len(self._flows) >= self._MAX_FLOWS:
            oldest_id = min(
                self._flows, key=lambda fid: self._flows[fid].created_at
            )
            del self._flows[oldest_id]

    def log_event(
        self,
        case_id: str,
        activity: str,
        resource: str = "",
        cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EventLog:
        if not case_id:
            raise VertexGeoTsProcessError(
                "INVALID_INPUT", "case_id 不可为空"
            )
        if not activity:
            raise VertexGeoTsProcessError(
                "INVALID_INPUT", "activity 不可为空"
            )
        event = EventLog(
            case_id=case_id,
            activity=activity,
            resource=resource,
            cost=cost,
            metadata=metadata or {},
        )
        with self._lock:
            self._evict_logs()
            self._logs[event.id] = event
        return event

    def get_event(self, event_id: str) -> EventLog:
        with self._lock:
            event = self._logs.get(event_id)
        if event is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"event {event_id} not found"
            )
        return event

    def list_events(
        self,
        case_id: str | None = None,
        activity: str | None = None,
    ) -> list[EventLog]:
        with self._lock:
            results = list(self._logs.values())
        if case_id is not None:
            results = [e for e in results if e.case_id == case_id]
        if activity is not None:
            results = [e for e in results if e.activity == activity]
        return sorted(results, key=lambda e: e.timestamp)

    def delete_event(self, event_id: str) -> bool:
        with self._lock:
            return self._logs.pop(event_id, None) is not None

    def discover_flow(
        self, name: str, case_ids: list[str] | None = None
    ) -> ProcessFlow:
        if not name:
            raise VertexGeoTsProcessError("INVALID_INPUT", "name 不可为空")
        with self._lock:
            events = list(self._logs.values())
        if case_ids is not None:
            case_id_set = set(case_ids)
            events = [e for e in events if e.case_id in case_id_set]
        # 按 case 分组并按时间排序
        by_case: dict[str, list[EventLog]] = {}
        for e in events:
            by_case.setdefault(e.case_id, []).append(e)
        for evts in by_case.values():
            evts.sort(key=lambda e: e.timestamp)
        # 唯一活动
        activities_set: set[str] = set()
        for e in events:
            activities_set.add(e.activity)
        activities = sorted(activities_set)
        # 转移：同 case 内连续活动对
        transition_counts: dict[tuple[str, str], int] = {}
        gap_by_activity: dict[str, list[float]] = {}
        all_gaps: list[float] = []
        for evts in by_case.values():
            for i in range(len(evts)):
                if i >= 1:
                    prev = evts[i - 1]
                    cur = evts[i]
                    key = (prev.activity, cur.activity)
                    transition_counts[key] = transition_counts.get(key, 0) + 1
                    gap = cur.timestamp - prev.timestamp
                    gap_by_activity.setdefault(cur.activity, []).append(gap)
                    all_gaps.append(gap)
        transitions = [
            {"from": a, "to": b, "count": c}
            for (a, b), c in sorted(transition_counts.items())
        ]
        # 瓶颈：平均时间间隔 > 全局平均间隔
        overall_avg = sum(all_gaps) / len(all_gaps) if all_gaps else 0.0
        bottlenecks: list[dict[str, Any]] = []
        for activity_name, gaps in gap_by_activity.items():
            avg_gap = sum(gaps) / len(gaps) if gaps else 0.0
            if overall_avg > 0 and avg_gap > overall_avg:
                bottlenecks.append(
                    {
                        "activity": activity_name,
                        "avg_gap_seconds": avg_gap,
                    }
                )
        bottlenecks.sort(key=lambda b: b["avg_gap_seconds"], reverse=True)
        flow = ProcessFlow(
            name=name,
            activities=activities,
            transitions=transitions,
            bottlenecks=bottlenecks,
            case_count=len(by_case),
        )
        with self._lock:
            self._evict_flows()
            self._flows[flow.id] = flow
        return flow

    def get_flow(self, flow_id: str) -> ProcessFlow:
        with self._lock:
            flow = self._flows.get(flow_id)
        if flow is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"flow {flow_id} not found"
            )
        return flow

    def list_flows(self) -> list[ProcessFlow]:
        with self._lock:
            results = list(self._flows.values())
        return sorted(results, key=lambda f: f.created_at)

    def get_flow_analysis(self, flow_id: str) -> dict[str, Any]:
        with self._lock:
            flow = self._flows.get(flow_id)
            if flow is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"flow {flow_id} not found"
                )
            events = list(self._logs.values())
        # 重建该 flow 涉及 case 的成本
        activity_set = set(flow.activities)
        relevant_case_ids = {
            e.case_id for e in events if e.activity in activity_set
        }
        total_cost = sum(
            e.cost for e in events if e.case_id in relevant_case_ids
        )
        case_count = flow.case_count
        avg_cost_per_case = (
            total_cost / case_count if case_count > 0 else 0.0
        )
        return {
            "flow_id": flow_id,
            "total_activities": len(flow.activities),
            "total_transitions": len(flow.transitions),
            "bottleneck_count": len(flow.bottlenecks),
            "avg_cost_per_case": avg_cost_per_case,
            "case_count": case_count,
        }

    def delete_flow(self, flow_id: str) -> bool:
        with self._lock:
            return self._flows.pop(flow_id, None) is not None


# ════════════════════ #35 Hyperauto ════════════════════

class IntegrationConfig(BaseModel):
    id: str = Field(default_factory=lambda: _uid("integ"))
    source_system: str  # erp/crm/scada/iot
    sync_enabled: bool = True
    auto_ontology_mapping: bool = True
    sync_interval_seconds: int = 300
    last_sync_at: float = 0
    status: str  # active/paused/error
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=_now_ts)


class SyncRecord(BaseModel):
    id: str = Field(default_factory=lambda: _uid("syncrec"))
    integration_id: str
    records_synced: int = 0
    objects_created: int = 0
    objects_updated: int = 0
    errors: int = 0
    started_at: float = Field(default_factory=_now_ts)
    completed_at: float = 0
    status: str  # running/completed/failed


class HyperautoEngine:
    """#35 Hyperauto 开箱集成引擎。"""

    _MAX_INTEGRATIONS = 200
    _MAX_SYNCS = 200
    _VALID_SOURCE_SYSTEMS = {"erp", "crm", "scada", "iot"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._integrations: dict[str, IntegrationConfig] = {}
        self._syncs: dict[str, SyncRecord] = {}

    def _evict_integrations(self) -> None:
        if len(self._integrations) >= self._MAX_INTEGRATIONS:
            oldest_id = min(
                self._integrations,
                key=lambda iid: self._integrations[iid].created_at,
            )
            del self._integrations[oldest_id]

    def _evict_syncs(self) -> None:
        if len(self._syncs) >= self._MAX_SYNCS:
            oldest_id = min(
                self._syncs,
                key=lambda sid: self._syncs[sid].started_at,
            )
            del self._syncs[oldest_id]

    def register_integration(
        self,
        source_system: str,
        sync_enabled: bool = True,
        auto_ontology_mapping: bool = True,
        sync_interval_seconds: int = 300,
        config: dict | None = None,
    ) -> IntegrationConfig:
        if source_system not in self._VALID_SOURCE_SYSTEMS:
            raise VertexGeoTsProcessError(
                "INVALID_SOURCE_SYSTEM",
                f"source_system must be one of {sorted(self._VALID_SOURCE_SYSTEMS)}",
            )
        integration = IntegrationConfig(
            source_system=source_system,
            sync_enabled=sync_enabled,
            auto_ontology_mapping=auto_ontology_mapping,
            sync_interval_seconds=sync_interval_seconds,
            status="active",
            config=config or {},
        )
        with self._lock:
            self._evict_integrations()
            self._integrations[integration.id] = integration
        return integration

    def get_integration(self, integration_id: str) -> IntegrationConfig:
        with self._lock:
            integration = self._integrations.get(integration_id)
        if integration is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"integration {integration_id} not found"
            )
        return integration

    def list_integrations(
        self,
        source_system: str | None = None,
        status: str | None = None,
    ) -> list[IntegrationConfig]:
        with self._lock:
            results = list(self._integrations.values())
        if source_system is not None:
            results = [i for i in results if i.source_system == source_system]
        if status is not None:
            results = [i for i in results if i.status == status]
        return sorted(results, key=lambda i: i.created_at)

    def update_integration(
        self, integration_id: str, updates: dict[str, Any]
    ) -> IntegrationConfig:
        with self._lock:
            integration = self._integrations.get(integration_id)
            if integration is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"integration {integration_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(integration).model_fields
            }
            updated = integration.model_copy(update=applicable)
            self._integrations[integration_id] = updated
        return updated

    def pause_integration(self, integration_id: str) -> IntegrationConfig:
        with self._lock:
            integration = self._integrations.get(integration_id)
            if integration is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"integration {integration_id} not found"
                )
            updated = integration.model_copy(update={"status": "paused"})
            self._integrations[integration_id] = updated
        return updated

    def resume_integration(self, integration_id: str) -> IntegrationConfig:
        with self._lock:
            integration = self._integrations.get(integration_id)
            if integration is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"integration {integration_id} not found"
                )
            updated = integration.model_copy(update={"status": "active"})
            self._integrations[integration_id] = updated
        return updated

    def delete_integration(self, integration_id: str) -> bool:
        with self._lock:
            existed = self._integrations.pop(integration_id, None) is not None
            if existed:
                # 同步清理该 integration 下的 syncs
                for sid in [
                    s.id
                    for s in self._syncs.values()
                    if s.integration_id == integration_id
                ]:
                    self._syncs.pop(sid, None)
            return existed

    def run_sync(self, integration_id: str) -> SyncRecord:
        with self._lock:
            integration = self._integrations.get(integration_id)
            if integration is None:
                raise VertexGeoTsProcessError(
                    "NOT_FOUND", f"integration {integration_id} not found"
                )
            if integration.status != "active":
                raise VertexGeoTsProcessError(
                    "INVALID_STATUS",
                    f"integration {integration_id} is not active",
                )
        sync = SyncRecord(
            integration_id=integration_id,
            records_synced=random.randint(10, 100),
            objects_created=random.randint(0, 20),
            objects_updated=random.randint(0, 30),
            errors=random.randint(0, 5),
            status="running",
        )
        sync.status = "completed"
        sync.completed_at = _now_ts()
        with self._lock:
            self._evict_syncs()
            self._syncs[sync.id] = sync
            integration = self._integrations.get(integration_id)
            if integration is not None:
                updated = integration.model_copy(
                    update={"last_sync_at": sync.completed_at}
                )
                self._integrations[integration_id] = updated
        return sync

    def get_sync(self, sync_id: str) -> SyncRecord:
        with self._lock:
            sync = self._syncs.get(sync_id)
        if sync is None:
            raise VertexGeoTsProcessError(
                "NOT_FOUND", f"sync {sync_id} not found"
            )
        return sync

    def list_syncs(
        self,
        integration_id: str | None = None,
        status: str | None = None,
    ) -> list[SyncRecord]:
        with self._lock:
            results = list(self._syncs.values())
        if integration_id is not None:
            results = [s for s in results if s.integration_id == integration_id]
        if status is not None:
            results = [s for s in results if s.status == status]
        return sorted(results, key=lambda s: s.started_at)

    def delete_sync(self, sync_id: str) -> bool:
        with self._lock:
            return self._syncs.pop(sync_id, None) is not None


# ────────────────────────────────────────────────────────────────
# 单例 getter（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_twin_engine: DigitalTwinEngine | None = None
_geo_ts_engine: GeoTimeSeriesEngine | None = None
_process_engine: ProcessMiningEngine | None = None
_hyperauto_engine: HyperautoEngine | None = None


def get_digital_twin_engine() -> DigitalTwinEngine:
    global _twin_engine
    if _twin_engine is None:
        with _lock:
            if _twin_engine is None:
                _twin_engine = DigitalTwinEngine()
    return _twin_engine


def get_geo_time_series_engine() -> GeoTimeSeriesEngine:
    global _geo_ts_engine
    if _geo_ts_engine is None:
        with _lock:
            if _geo_ts_engine is None:
                _geo_ts_engine = GeoTimeSeriesEngine()
    return _geo_ts_engine


def get_process_mining_engine() -> ProcessMiningEngine:
    global _process_engine
    if _process_engine is None:
        with _lock:
            if _process_engine is None:
                _process_engine = ProcessMiningEngine()
    return _process_engine


def get_hyperauto_engine() -> HyperautoEngine:
    global _hyperauto_engine
    if _hyperauto_engine is None:
        with _lock:
            if _hyperauto_engine is None:
                _hyperauto_engine = HyperautoEngine()
    return _hyperauto_engine
