"""W2-AG · Data Connection 管理组（#114 / #115）.

- #114 AgentAdminEngine：Agent 管理面（注册/下载/心跳/日志/驱动/证书/自动升级）
- #115 SourceExplorerEngine：源探索（ER 关系图/资源树/样本预览）

详见 docs/palantier/20_tech/220tech_w2-ag-column-impact.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_VALID_ADMIN_STATUSES = {"registered", "active", "deprecated"}
_VALID_DRIVER_TYPES = {"jdbc", "odbc", "python", "generic"}
_VALID_LOG_LEVELS = {"info", "warn", "error"}

_VALID_RELATION_TYPES = {"one_to_one", "one_to_many", "many_to_one", "many_to_many"}
_VALID_RESOURCE_TYPES = {"database", "schema", "table", "column"}

_MAX_ADMINS = 200
_MAX_LOGS = 200
_MAX_SCHEMAS = 200


# ════════════════════ 数据模型 ════════════════════

class AgentDriver(BaseModel):
    """驱动元数据。"""
    name: str
    version: str
    type: str                 # jdbc / odbc / python / generic


class AgentCertificate(BaseModel):
    """证书元数据。"""
    id: str = Field(default_factory=lambda: "cert-" + uuid.uuid4().hex[:8])
    name: str
    issuer: str = ""
    expires_at: float = 0.0


class AgentLogEntry(BaseModel):
    """Agent 日志条目。"""
    timestamp: float = Field(default_factory=lambda: time.time())
    level: str                # info / warn / error
    message: str


class AgentAdmin(BaseModel):
    """Data Connection Agent 管理记录。"""
    id: str = Field(default_factory=lambda: "adm-" + uuid.uuid4().hex[:10])
    agent_id: str
    name: str
    version: str = "1.0.0"
    status: str = "registered"        # registered / active / deprecated
    download_url: str = ""
    drivers: list[AgentDriver] = Field(default_factory=list)
    certificates: list[AgentCertificate] = Field(default_factory=list)
    logs: list[AgentLogEntry] = Field(default_factory=list)
    auto_upgrade: bool = False
    last_heartbeat: float = 0.0
    created_at: float = Field(default_factory=lambda: time.time())


class ERRelation(BaseModel):
    """ER 关系。"""
    from_table: str
    to_table: str
    from_column: str
    to_column: str
    relation_type: str = "many_to_one"


class ResourceNode(BaseModel):
    """资源树节点。"""
    name: str
    type: str                             # database / schema / table / column
    children: list[str] = Field(default_factory=list)


class SourceSchema(BaseModel):
    """数据源 schema 探索记录。"""
    id: str = Field(default_factory=lambda: "sch-" + uuid.uuid4().hex[:10])
    source_id: str
    dataset_name: str
    er_diagram: list[ERRelation] = Field(default_factory=list)
    resource_tree: list[ResourceNode] = Field(default_factory=list)
    sample_preview: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())


# ════════════════════ 错误 ════════════════════

class DataConnectionAdminError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ #114 AgentAdminEngine ════════════════════

class AgentAdminEngine:
    def __init__(self) -> None:
        self._admins: dict[str, AgentAdmin] = {}
        self._lock = threading.Lock()

    def register(self, admin: AgentAdmin) -> AgentAdmin:
        if not admin.agent_id:
            raise DataConnectionAdminError("MISSING_AGENT", "agent_id 不能为空")
        if not admin.name:
            raise DataConnectionAdminError("MISSING_NAME", "name 不能为空")
        # driver 校验
        for drv in admin.drivers:
            if drv.type not in _VALID_DRIVER_TYPES:
                raise DataConnectionAdminError(
                    "INVALID_DRIVER_TYPE", f"未知驱动类型：{drv.type}",
                )
        with self._lock:
            if len(self._admins) >= _MAX_ADMINS:
                oldest_id = next(iter(self._admins))
                self._admins.pop(oldest_id, None)
            self._admins[admin.id] = admin
        return admin

    def get(self, admin_id: str) -> AgentAdmin:
        a = self._admins.get(admin_id)
        if a is None:
            raise DataConnectionAdminError("NOT_FOUND", f"Agent 管理 {admin_id} 不存在")
        return a

    def list(
        self, agent_id: str | None = None, status: str | None = None,
    ) -> list[AgentAdmin]:
        items = list(self._admins.values())
        if agent_id:
            items = [a for a in items if a.agent_id == agent_id]
        if status:
            items = [a for a in items if a.status == status]
        return items

    def update(self, admin_id: str, updates: dict[str, Any]) -> AgentAdmin:
        a = self.get(admin_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if k == "drivers" and isinstance(v, list):
                for drv in v:
                    dtype = drv.type if hasattr(drv, "type") else drv.get("type", "")
                    if dtype not in _VALID_DRIVER_TYPES:
                        raise DataConnectionAdminError(
                            "INVALID_DRIVER_TYPE", f"未知驱动类型：{dtype}",
                        )
            if hasattr(a, k):
                setattr(a, k, v)
        return a

    def delete(self, admin_id: str) -> bool:
        return self._admins.pop(admin_id, None) is not None

    def heartbeat(self, admin_id: str) -> AgentAdmin:
        a = self.get(admin_id)
        a.last_heartbeat = time.time()
        if a.status == "registered":
            a.status = "active"
        return a

    def push_log(self, admin_id: str, level: str, message: str) -> AgentAdmin:
        if level not in _VALID_LOG_LEVELS:
            raise DataConnectionAdminError(
                "INVALID_LOG_LEVEL", f"未知日志级别：{level}",
            )
        a = self.get(admin_id)
        entry = AgentLogEntry(level=level, message=message)
        with self._lock:
            if len(a.logs) >= _MAX_LOGS:
                a.logs.pop(0)
            a.logs.append(entry)
        return a

    def upgrade(self, admin_id: str, new_version: str) -> AgentAdmin:
        if not new_version:
            raise DataConnectionAdminError("MISSING_VERSION", "新版本号不能为空")
        a = self.get(admin_id)
        a.version = new_version
        a.status = "active"
        return a

    def list_drivers(self, admin_id: str) -> list[AgentDriver]:
        a = self.get(admin_id)
        return list(a.drivers)

    def list_certificates(self, admin_id: str) -> list[AgentCertificate]:
        a = self.get(admin_id)
        return list(a.certificates)

    def get_download_url(self, admin_id: str) -> str:
        a = self.get(admin_id)
        if a.status == "deprecated":
            raise DataConnectionAdminError(
                "AGENT_DEPRECATED", f"Agent {a.agent_id} 已弃用，不可下载",
            )
        return a.download_url


# ════════════════════ #115 SourceExplorerEngine ════════════════════

class SourceExplorerEngine:
    def __init__(self) -> None:
        self._schemas: dict[str, SourceSchema] = {}
        self._lock = threading.Lock()

    def register(self, schema: SourceSchema) -> SourceSchema:
        if not schema.source_id:
            raise DataConnectionAdminError("MISSING_SOURCE", "source_id 不能为空")
        if not schema.dataset_name:
            raise DataConnectionAdminError("MISSING_DATASET_NAME", "dataset_name 不能为空")
        for rel in schema.er_diagram:
            if rel.relation_type not in _VALID_RELATION_TYPES:
                raise DataConnectionAdminError(
                    "INVALID_RELATION_TYPE", f"未知关系类型：{rel.relation_type}",
                )
        for node in schema.resource_tree:
            if node.type not in _VALID_RESOURCE_TYPES:
                raise DataConnectionAdminError(
                    "INVALID_RESOURCE_TYPE", f"未知资源类型：{node.type}",
                )
        with self._lock:
            if len(self._schemas) >= _MAX_SCHEMAS:
                oldest_id = next(iter(self._schemas))
                self._schemas.pop(oldest_id, None)
            self._schemas[schema.id] = schema
        return schema

    def get(self, schema_id: str) -> SourceSchema:
        s = self._schemas.get(schema_id)
        if s is None:
            raise DataConnectionAdminError("NOT_FOUND", f"schema {schema_id} 不存在")
        return s

    def list(self, source_id: str | None = None) -> list[SourceSchema]:
        items = list(self._schemas.values())
        if source_id:
            items = [s for s in items if s.source_id == source_id]
        return items

    def update(self, schema_id: str, updates: dict[str, Any]) -> SourceSchema:
        s = self.get(schema_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if k == "er_diagram" and isinstance(v, list):
                for rel in v:
                    rtype = rel.relation_type if hasattr(rel, "relation_type") else rel.get("relation_type", "")
                    if rtype not in _VALID_RELATION_TYPES:
                        raise DataConnectionAdminError(
                            "INVALID_RELATION_TYPE", f"未知关系类型：{rtype}",
                        )
            if k == "resource_tree" and isinstance(v, list):
                for node in v:
                    ntype = node.type if hasattr(node, "type") else node.get("type", "")
                    if ntype not in _VALID_RESOURCE_TYPES:
                        raise DataConnectionAdminError(
                            "INVALID_RESOURCE_TYPE", f"未知资源类型：{ntype}",
                        )
            if hasattr(s, k):
                setattr(s, k, v)
        return s

    def delete(self, schema_id: str) -> bool:
        return self._schemas.pop(schema_id, None) is not None

    def explore_er(self, schema_id: str) -> list[ERRelation]:
        s = self.get(schema_id)
        return list(s.er_diagram)

    def explore_resource_tree(self, schema_id: str) -> list[ResourceNode]:
        s = self.get(schema_id)
        return list(s.resource_tree)

    def preview_sample(self, schema_id: str, limit: int = 10) -> list[dict[str, Any]]:
        s = self.get(schema_id)
        if limit <= 0:
            return list(s.sample_preview)
        return list(s.sample_preview[:limit])


# ════════════════════ 单例 ════════════════════

_admin_engine: AgentAdminEngine | None = None
_explorer_engine: SourceExplorerEngine | None = None
_singleton_lock = threading.Lock()


def get_admin_engine() -> AgentAdminEngine:
    global _admin_engine
    if _admin_engine is None:
        with _singleton_lock:
            if _admin_engine is None:
                _admin_engine = AgentAdminEngine()
    return _admin_engine


def get_explorer_engine() -> SourceExplorerEngine:
    global _explorer_engine
    if _explorer_engine is None:
        with _singleton_lock:
            if _explorer_engine is None:
                _explorer_engine = SourceExplorerEngine()
    return _explorer_engine
