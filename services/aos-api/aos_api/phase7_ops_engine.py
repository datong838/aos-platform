"""Phase 7 · Ops Delivery Engine.

Hub + Spokes (plan/plan-diff/config/maintenance-window) + Releases (rc/beta/stable/hotfix/recall) + Ferry (bundles/submit).
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


# ───────────────────────── Pydantic Models ─────────────────────────


class HubInfo(BaseModel):
    id: str = "hub-001"
    version: str = "3.14.0"
    cluster: str = "aos-prod"
    status: str = "healthy"  # healthy|degraded|error
    region: str = "us-east-1"
    uptime_days: int = 45
    last_health_check: float = Field(default_factory=lambda: time.time())
    spokes_count: int = 5
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpokeSummary(BaseModel):
    id: str = Field(default_factory=lambda: "spoke-" + uuid.uuid4().hex[:8])
    name: str
    hub_id: str = "hub-001"
    region: str = "us-east-1"
    status: str = "healthy"  # healthy|degraded|error|unreachable|maintenance
    version: str = "3.14.0"
    url: str = ""
    last_seen: float = Field(default_factory=lambda: time.time())
    created_at: float = Field(default_factory=lambda: time.time())


class SpokeDetail(SpokeSummary):
    description: str = ""
    config_hash: str = ""
    plan_version: str = "v1"
    resources: dict[str, Any] = Field(default_factory=dict)
    health_checks: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    updated_at: float = Field(default_factory=lambda: time.time())


class PlanItem(BaseModel):
    id: str = Field(default_factory=lambda: "plan-" + uuid.uuid4().hex[:8])
    spoke_id: str
    action: str = "deploy"  # deploy|upgrade|rollback|scale|config
    resource: str = ""
    current_state: str = ""
    target_state: str = ""
    status: str = "pending"  # pending|applying|applied|failed
    created_at: float = Field(default_factory=lambda: time.time())


class PlanDiffEntry(BaseModel):
    path: str
    current_value: Any = None
    target_value: Any = None
    diff_type: str = "modified"  # added|removed|modified


class SpokeConfig(BaseModel):
    spoke_id: str
    overrides: dict[str, Any] = Field(default_factory=dict)
    effective_config: dict[str, Any] = Field(default_factory=dict)
    base_config: dict[str, Any] = Field(default_factory=dict)
    last_updated: float = Field(default_factory=lambda: time.time())
    updated_by: str = "system"


class MaintenanceWindow(BaseModel):
    id: str = Field(default_factory=lambda: "mw-" + uuid.uuid4().hex[:8])
    spoke_id: str
    start_time: float = Field(default_factory=lambda: time.time())
    end_time: float = Field(default_factory=lambda: time.time() + 7200)
    reason: str = "scheduled upgrade"
    status: str = "scheduled"  # scheduled|active|completed|cancelled
    created_by: str = "system"


class ReleaseItem(BaseModel):
    id: str = Field(default_factory=lambda: "rel-" + uuid.uuid4().hex[:8])
    channel: str = "stable"  # rc|beta|stable
    version: str = "3.14.0"
    released_at: float = Field(default_factory=lambda: time.time())
    changelog: list[str] = Field(default_factory=list)
    commit_hash: str = ""
    artifacts: list[str] = Field(default_factory=list)
    status: str = "published"  # published|draft|recalled


class HotfixInfo(BaseModel):
    id: str = Field(default_factory=lambda: "hfx-" + uuid.uuid4().hex[:8])
    version: str = "3.14.0-hotfix.1"
    base_version: str = "3.14.0"
    description: str = ""
    created_at: float = Field(default_factory=lambda: time.time())
    pushed_at: float = 0.0
    status: str = "ready"  # ready|pushed|failed
    target_spokes: list[str] = Field(default_factory=list)


class RecallRecord(BaseModel):
    id: str = Field(default_factory=lambda: "rcl-" + uuid.uuid4().hex[:8])
    from_version: str = ""
    to_version: str = ""
    reason: str = ""
    executed_at: float = Field(default_factory=lambda: time.time())
    executed_by: str = "system"
    status: str = "completed"  # completed|failed|pending


class FerryBundle(BaseModel):
    id: str = Field(default_factory=lambda: "bun-" + uuid.uuid4().hex[:8])
    name: str
    version: str = "1.0.0"
    size_mb: float = 0.0
    created_at: float = Field(default_factory=lambda: time.time())
    artifacts: list[str] = Field(default_factory=list)
    status: str = "ready"  # ready|ferrying|ferried|failed
    description: str = ""


class FerrySubmitRequest(BaseModel):
    bundle_id: str
    spoke_ids: list[str] = Field(default_factory=list)


class FerrySubmission(BaseModel):
    id: str = Field(default_factory=lambda: "fer-" + uuid.uuid4().hex[:8])
    bundle_id: str
    spoke_ids: list[str] = Field(default_factory=list)
    submitted_at: float = Field(default_factory=lambda: time.time())
    status: str = "submitted"  # submitted|in_transit|delivered|failed


# ───────────────────────── Engine ─────────────────────────


class OpsDeliveryEngine:
    """Singleton engine for Phase 7 Ops Delivery."""

    _instance: "OpsDeliveryEngine | None" = None
    _engine_lock = threading.Lock()

    def __new__(cls) -> "OpsDeliveryEngine":
        with cls._engine_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._hub: HubInfo | None = None
        self._spokes: dict[str, SpokeDetail] = {}
        self._plan_items: dict[str, list[PlanItem]] = {}  # spoke_id -> items
        self._plan_diffs: dict[str, list[PlanDiffEntry]] = {}  # spoke_id -> diffs
        self._spoke_configs: dict[str, SpokeConfig] = {}
        self._maintenance_windows: dict[str, list[MaintenanceWindow]] = {}  # spoke_id -> windows
        self._releases: dict[str, ReleaseItem] = {}
        self._hotfixes: dict[str, HotfixInfo] = {}
        self._recalls: dict[str, RecallRecord] = {}
        self._ferry_bundles: dict[str, FerryBundle] = {}
        self._ferry_submissions: dict[str, FerrySubmission] = {}

    # ── Hub ──

    def get_hub(self) -> HubInfo:
        if self._hub is None:
            self._hub = HubInfo()
        return self._hub

    def update_hub(self, **kwargs: Any) -> HubInfo:
        with _LOCK:
            hub = self.get_hub()
            for k, v in kwargs.items():
                if hasattr(hub, k):
                    setattr(hub, k, v)
            hub.last_health_check = time.time()
            return hub

    # ── Spokes ──

    def create_spoke(self, name: str, **kwargs: Any) -> SpokeDetail:
        with _LOCK:
            s = SpokeDetail(name=name, **kwargs)
            self._spokes[s.id] = s
            self._update_hub_spoke_count()
            return s

    def get_spoke(self, sid: str) -> SpokeDetail | None:
        return self._spokes.get(sid)

    def list_spokes(
        self, status: str | None = None, hub_id: str | None = None,
        page: int = 1, page_size: int = 50,
    ) -> tuple[list[SpokeSummary], int]:
        items = list(self._spokes.values())
        if status:
            items = [s for s in items if s.status == status]
        if hub_id:
            items = [s for s in items if s.hub_id == hub_id]
        total = len(items)
        start = (page - 1) * page_size
        page_items = items[start : start + page_size]
        # Return as SpokeSummary (lighter view)
        summaries = [
            SpokeSummary(
                id=s.id, name=s.name, hub_id=s.hub_id, region=s.region,
                status=s.status, version=s.version, url=s.url,
                last_seen=s.last_seen, created_at=s.created_at,
            )
            for s in page_items
        ]
        return summaries, total

    def update_spoke(self, sid: str, **kwargs: Any) -> SpokeDetail:
        with _LOCK:
            s = self._spokes.get(sid)
            if s is None:
                raise KeyError(f"Spoke {sid} not found")
            for k, v in kwargs.items():
                if hasattr(s, k) and k != "id":
                    setattr(s, k, v)
            s.updated_at = time.time()
            return s

    def delete_spoke(self, sid: str) -> bool:
        with _LOCK:
            existed = sid in self._spokes
            self._spokes.pop(sid, None)
            if existed:
                self._update_hub_spoke_count()
            return existed

    def _update_hub_spoke_count(self) -> None:
        hub = self.get_hub()
        hub.spokes_count = len(self._spokes)

    # ── Plan ──

    def get_spoke_plan(self, spoke_id: str) -> list[PlanItem]:
        if spoke_id not in self._spokes:
            raise KeyError(f"Spoke {spoke_id} not found")
        return self._plan_items.get(spoke_id, [])

    def add_plan_item(self, spoke_id: str, **kwargs: Any) -> PlanItem:
        with _LOCK:
            if spoke_id not in self._spokes:
                raise KeyError(f"Spoke {spoke_id} not found")
            item = PlanItem(spoke_id=spoke_id, **kwargs)
            self._plan_items.setdefault(spoke_id, []).append(item)
            return item

    def get_plan_diff(self, spoke_id: str) -> list[PlanDiffEntry]:
        if spoke_id not in self._spokes:
            raise KeyError(f"Spoke {spoke_id} not found")
        return self._plan_diffs.get(spoke_id, [])

    def add_plan_diff(self, spoke_id: str, **kwargs: Any) -> PlanDiffEntry:
        with _LOCK:
            if spoke_id not in self._spokes:
                raise KeyError(f"Spoke {spoke_id} not found")
            entry = PlanDiffEntry(**kwargs)
            self._plan_diffs.setdefault(spoke_id, []).append(entry)
            return entry

    # ── Spoke Config ──

    def get_spoke_config(self, spoke_id: str) -> SpokeConfig:
        if spoke_id not in self._spokes:
            raise KeyError(f"Spoke {spoke_id} not found")
        cfg = self._spoke_configs.get(spoke_id)
        if cfg is None:
            cfg = SpokeConfig(spoke_id=spoke_id)
            self._spoke_configs[spoke_id] = cfg
        return cfg

    def update_spoke_config(self, spoke_id: str, overrides: dict[str, Any], updated_by: str = "system") -> SpokeConfig:
        with _LOCK:
            if spoke_id not in self._spokes:
                raise KeyError(f"Spoke {spoke_id} not found")
            cfg = self._spoke_configs.get(spoke_id)
            if cfg is None:
                cfg = SpokeConfig(spoke_id=spoke_id)
                self._spoke_configs[spoke_id] = cfg
            cfg.overrides = overrides
            cfg.effective_config = {**cfg.base_config, **overrides}
            cfg.last_updated = time.time()
            cfg.updated_by = updated_by
            return cfg

    # ── Maintenance Windows ──

    def get_maintenance_windows(self, spoke_id: str) -> list[MaintenanceWindow]:
        if spoke_id not in self._spokes:
            raise KeyError(f"Spoke {spoke_id} not found")
        return self._maintenance_windows.get(spoke_id, [])

    def create_maintenance_window(self, spoke_id: str, **kwargs: Any) -> MaintenanceWindow:
        with _LOCK:
            if spoke_id not in self._spokes:
                raise KeyError(f"Spoke {spoke_id} not found")
            mw = MaintenanceWindow(spoke_id=spoke_id, **kwargs)
            self._maintenance_windows.setdefault(spoke_id, []).append(mw)
            return mw

    # ── Releases ──

    def create_release(self, channel: str, version: str, **kwargs: Any) -> ReleaseItem:
        with _LOCK:
            r = ReleaseItem(channel=channel, version=version, **kwargs)
            self._releases[r.id] = r
            return r

    def get_release(self, rid: str) -> ReleaseItem | None:
        return self._releases.get(rid)

    def list_releases(self, channel: str | None = None) -> list[ReleaseItem]:
        items = list(self._releases.values())
        if channel:
            items = [r for r in items if r.channel == channel]
        # Sort: rc -> beta -> stable, then newest first
        order = {"rc": 0, "beta": 1, "stable": 2}
        items.sort(key=lambda r: (order.get(r.channel, 9), -r.released_at))
        return items

    # ── Hotfix ──

    def get_current_hotfix(self) -> HotfixInfo | None:
        # Return the most recent hotfix
        items = list(self._hotfixes.values())
        if not items:
            return None
        items.sort(key=lambda h: h.created_at, reverse=True)
        return items[0]

    def create_hotfix(self, version: str, **kwargs: Any) -> HotfixInfo:
        with _LOCK:
            h = HotfixInfo(version=version, **kwargs)
            self._hotfixes[h.id] = h
            return h

    def push_hotfix(self, hid: str) -> HotfixInfo:
        with _LOCK:
            h = self._hotfixes.get(hid)
            if h is None:
                raise KeyError(f"Hotfix {hid} not found")
            h.status = "pushed"
            h.pushed_at = time.time()
            return h

    # ── Recall ──

    def list_recalls(self, limit: int = 20) -> list[RecallRecord]:
        items = list(self._recalls.values())
        items.sort(key=lambda r: r.executed_at, reverse=True)
        return items[:limit]

    def create_recall(self, from_version: str, to_version: str, reason: str = "") -> RecallRecord:
        with _LOCK:
            r = RecallRecord(from_version=from_version, to_version=to_version, reason=reason)
            self._recalls[r.id] = r
            return r

    def execute_recall(self, rid: str) -> RecallRecord:
        with _LOCK:
            r = self._recalls.get(rid)
            if r is None:
                raise KeyError(f"Recall {rid} not found")
            r.status = "completed"
            r.executed_at = time.time()
            return r

    # ── Ferry ──

    def create_bundle(self, name: str, **kwargs: Any) -> FerryBundle:
        with _LOCK:
            b = FerryBundle(name=name, **kwargs)
            self._ferry_bundles[b.id] = b
            return b

    def list_bundles(self) -> list[FerryBundle]:
        items = list(self._ferry_bundles.values())
        items.sort(key=lambda b: b.created_at, reverse=True)
        return items

    def get_bundle(self, bid: str) -> FerryBundle | None:
        return self._ferry_bundles.get(bid)

    def submit_ferry(self, bundle_id: str, spoke_ids: list[str]) -> FerrySubmission:
        with _LOCK:
            if bundle_id not in self._ferry_bundles:
                raise KeyError(f"Bundle {bundle_id} not found")
            for sid in spoke_ids:
                if sid not in self._spokes:
                    raise KeyError(f"Spoke {sid} not found")
            sub = FerrySubmission(bundle_id=bundle_id, spoke_ids=spoke_ids)
            self._ferry_submissions[sub.id] = sub
            return sub

    # ── Util ──

    def reset(self) -> None:
        with _LOCK:
            self._hub = None
            self._spokes.clear()
            self._plan_items.clear()
            self._plan_diffs.clear()
            self._spoke_configs.clear()
            self._maintenance_windows.clear()
            self._releases.clear()
            self._hotfixes.clear()
            self._recalls.clear()
            self._ferry_bundles.clear()
            self._ferry_submissions.clear()
            self._initialized = False


def get_engine() -> OpsDeliveryEngine:
    return OpsDeliveryEngine()
