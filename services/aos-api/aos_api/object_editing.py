"""W2-N · Object 编辑增强：冲突解决 + 模式迁移 + 编辑历史追踪."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ─────────────── #42 对象编辑冲突解决 ───────────────

class EditConflict(BaseModel):
    id: str = Field(default_factory=lambda: _uid("conf"))
    object_type: str
    object_id: str
    field: str
    edit_a: dict[str, Any] = Field(default_factory=dict)   # {user, value, timestamp}
    edit_b: dict[str, Any] = Field(default_factory=dict)
    resolution: dict[str, Any] | None = None


class ConflictResolution(BaseModel):
    strategy: str
    winner: str            # "a" / "b"
    resolved_value: Any
    reason: str


class ConflictError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ConflictEngine:
    """对象编辑冲突检测与解决引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conflicts: dict[str, EditConflict] = {}
        self._user_priorities: dict[str, int] = {}  # user -> priority level (higher=more important)

    def set_user_priority(self, user: str, priority: int) -> None:
        with self._lock:
            self._user_priorities[user] = priority

    def detect(
        self,
        object_type: str,
        object_id: str,
        field: str,
        edit_a: dict[str, Any],
        edit_b: dict[str, Any],
    ) -> EditConflict:
        """检测并记录冲突。"""
        conflict = EditConflict(
            object_type=object_type,
            object_id=object_id,
            field=field,
            edit_a=edit_a,
            edit_b=edit_b,
        )
        with self._lock:
            self._conflicts[conflict.id] = conflict
        return conflict

    def resolve(
        self,
        conflict_id: str,
        strategy: str = "timestamp_priority",
    ) -> EditConflict:
        """按指定策略解决冲突。"""
        with self._lock:
            conflict = self._conflicts.get(conflict_id)
            if not conflict:
                raise ConflictError("NOT_FOUND", f"冲突 {conflict_id} 不存在")
            if conflict.resolution is not None:
                raise ConflictError("ALREADY_RESOLVED", f"冲突 {conflict_id} 已解决")

            edit_a = conflict.edit_a
            edit_b = conflict.edit_b

            if strategy == "user_priority":
                user_a = edit_a.get("user", "")
                user_b = edit_b.get("user", "")
                prio_a = self._user_priorities.get(user_a, 0)
                prio_b = self._user_priorities.get(user_b, 0)
                if prio_a >= prio_b:
                    winner = "a"
                    resolved_value = edit_a.get("value")
                    reason = f"用户 {user_a} 优先级 {prio_a} >= {user_b} 优先级 {prio_b}"
                else:
                    winner = "b"
                    resolved_value = edit_b.get("value")
                    reason = f"用户 {user_b} 优先级 {prio_b} > {user_a} 优先级 {prio_a}"
            elif strategy == "timestamp_priority":
                ts_a = edit_a.get("timestamp", "")
                ts_b = edit_b.get("timestamp", "")
                if ts_a >= ts_b:
                    winner = "a"
                    resolved_value = edit_a.get("value")
                    reason = f"时间戳 {ts_a} >= {ts_b}"
                else:
                    winner = "b"
                    resolved_value = edit_b.get("value")
                    reason = f"时间戳 {ts_b} > {ts_a}"
            else:
                raise ConflictError("INVALID_STRATEGY", f"未知策略: {strategy}")

            conflict.resolution = ConflictResolution(
                strategy=strategy,
                winner=winner,
                resolved_value=resolved_value,
                reason=reason,
            ).model_dump()
            return conflict

    def get(self, conflict_id: str) -> EditConflict:
        with self._lock:
            conflict = self._conflicts.get(conflict_id)
            if not conflict:
                raise ConflictError("NOT_FOUND", f"冲突 {conflict_id} 不存在")
            return conflict

    def list(
        self,
        *,
        object_type: str | None = None,
        object_id: str | None = None,
        resolved: bool | None = None,
    ) -> list[EditConflict]:
        with self._lock:
            items = list(self._conflicts.values())
        result: list[EditConflict] = []
        for c in items:
            if object_type and c.object_type != object_type:
                continue
            if object_id and c.object_id != object_id:
                continue
            if resolved is not None:
                is_resolved = c.resolution is not None
                if resolved != is_resolved:
                    continue
            result.append(c)
        return result

    def reset(self) -> None:
        with self._lock:
            self._conflicts.clear()
            self._user_priorities.clear()


# ─────────────── #44 对象模式迁移 ───────────────

class MigrationCommand(BaseModel):
    id: str = Field(default_factory=lambda: _uid("mc"))
    object_type: str
    instruction: str   # ADD_PROPERTY / REMOVE_PROPERTY / RENAME_PROPERTY / CHANGE_TYPE / SET_NULLABLE
    field: str
    params: dict[str, Any] = Field(default_factory=dict)
    status: str = "PENDING"  # PENDING / RUNNING / COMPLETED / FAILED
    error: str = ""


class MigrationBatch(BaseModel):
    id: str = Field(default_factory=lambda: _uid("mb"))
    object_type: str
    commands: list[MigrationCommand] = Field(default_factory=list)
    total: int = 0
    processed: int = 0
    failed: int = 0
    status: str = "PENDING"  # PENDING / RUNNING / COMPLETED / FAILED
    dry_run: bool = False
    created_at: str = Field(default_factory=_now)


class MigrationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_INSTRUCTIONS = {
    "ADD_PROPERTY", "REMOVE_PROPERTY", "RENAME_PROPERTY", "CHANGE_TYPE", "SET_NULLABLE",
}

MAX_BATCH_SIZE = 500


class MigrationEngine:
    """对象模式迁移引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._batches: dict[str, MigrationBatch] = {}
        # 对象 schema 快照: object_type -> {properties: [{name, data_type, nullable}]}
        self._schemas: dict[str, list[dict[str, Any]]] = {}

    def register_schema(self, object_type: str, properties: list[dict[str, Any]]) -> None:
        with self._lock:
            self._schemas[object_type] = list(properties)

    def get_schema(self, object_type: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._schemas.get(object_type, []))

    def create_batch(
        self,
        object_type: str,
        commands: list[dict[str, Any]],
        *,
        dry_run: bool = False,
    ) -> MigrationBatch:
        """创建迁移批次。"""
        if len(commands) > MAX_BATCH_SIZE:
            raise MigrationError(
                "BATCH_TOO_LARGE",
                f"批次大小 {len(commands)} 超过上限 {MAX_BATCH_SIZE}",
            )
        validated: list[MigrationCommand] = []
        for cmd_dict in commands:
            instruction = cmd_dict.get("instruction", "")
            if instruction not in _VALID_INSTRUCTIONS:
                raise MigrationError(
                    "INVALID_INSTRUCTION",
                    f"未知迁移指令: {instruction}",
                )
            validated.append(MigrationCommand(
                object_type=object_type,
                instruction=instruction,
                field=cmd_dict.get("field", ""),
                params=cmd_dict.get("params", {}),
            ))
        batch = MigrationBatch(
            object_type=object_type,
            commands=validated,
            total=len(validated),
            dry_run=dry_run,
        )
        with self._lock:
            self._batches[batch.id] = batch
        return batch

    def execute_batch(self, batch_id: str) -> MigrationBatch:
        """执行迁移批次。"""
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                raise MigrationError("NOT_FOUND", f"迁移批次 {batch_id} 不存在")
            if batch.status in ("RUNNING", "COMPLETED"):
                raise MigrationError("ALREADY_RUNNING", f"批次 {batch_id} 状态为 {batch.status}")

            batch.status = "RUNNING"
            schema = list(self._schemas.get(batch.object_type, []))

            for cmd in batch.commands:
                cmd.status = "RUNNING"
                try:
                    schema = self._apply_instruction(schema, cmd)
                    cmd.status = "COMPLETED"
                    batch.processed += 1
                except Exception as exc:
                    cmd.status = "FAILED"
                    cmd.error = str(exc)
                    batch.failed += 1
                    if not batch.dry_run:
                        batch.status = "FAILED"
                        break
                    batch.processed += 1

            if batch.status != "FAILED":
                batch.status = "COMPLETED"
                if not batch.dry_run:
                    self._schemas[batch.object_type] = schema
            return batch

    def _apply_instruction(
        self,
        schema: list[dict[str, Any]],
        cmd: MigrationCommand,
    ) -> list[dict[str, Any]]:
        """应用单条迁移指令到 schema。"""
        field_name = cmd.field
        if cmd.instruction == "ADD_PROPERTY":
            for prop in schema:
                if prop.get("name") == field_name:
                    raise MigrationError("FIELD_EXISTS", f"属性 {field_name} 已存在")
            schema.append({
                "name": field_name,
                "data_type": cmd.params.get("data_type", "string"),
                "nullable": cmd.params.get("nullable", True),
            })
        elif cmd.instruction == "REMOVE_PROPERTY":
            schema = [p for p in schema if p.get("name") != field_name]
        elif cmd.instruction == "RENAME_PROPERTY":
            new_name = cmd.params.get("new_name", "")
            if not new_name:
                raise MigrationError("MISSING_PARAM", "RENAME_PROPERTY 需要 new_name 参数")
            for prop in schema:
                if prop.get("name") == field_name:
                    prop["name"] = new_name
                    break
            else:
                raise MigrationError("FIELD_NOT_FOUND", f"属性 {field_name} 不存在")
        elif cmd.instruction == "CHANGE_TYPE":
            new_type = cmd.params.get("data_type", "")
            if not new_type:
                raise MigrationError("MISSING_PARAM", "CHANGE_TYPE 需要 data_type 参数")
            for prop in schema:
                if prop.get("name") == field_name:
                    prop["data_type"] = new_type
                    break
            else:
                raise MigrationError("FIELD_NOT_FOUND", f"属性 {field_name} 不存在")
        elif cmd.instruction == "SET_NULLABLE":
            nullable = cmd.params.get("nullable", True)
            for prop in schema:
                if prop.get("name") == field_name:
                    prop["nullable"] = nullable
                    break
            else:
                raise MigrationError("FIELD_NOT_FOUND", f"属性 {field_name} 不存在")
        return schema

    def get_batch(self, batch_id: str) -> MigrationBatch:
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                raise MigrationError("NOT_FOUND", f"迁移批次 {batch_id} 不存在")
            return batch

    def list_batches(self, *, object_type: str | None = None) -> list[MigrationBatch]:
        with self._lock:
            batches = list(self._batches.values())
        if object_type:
            batches = [b for b in batches if b.object_type == object_type]
        return batches

    def reset(self) -> None:
        with self._lock:
            self._batches.clear()
            self._schemas.clear()


# ─────────────── #45 对象编辑历史追踪 ───────────────

class ObjectChangeLog(BaseModel):
    id: str = Field(default_factory=lambda: _uid("cl"))
    object_type: str
    object_id: str
    field: str
    old_value: Any = None
    new_value: Any = None
    author: str = ""
    timestamp: str = Field(default_factory=_now)
    operation: str = "update"  # create / update / delete


class ChangeLogError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ChangeLogEngine:
    """对象编辑历史追踪引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._logs: list[ObjectChangeLog] = []
        self._enabled: dict[str, bool] = {}  # object_type -> enabled

    def enable(self, object_type: str) -> None:
        with self._lock:
            self._enabled[object_type] = True

    def disable(self, object_type: str) -> None:
        with self._lock:
            self._enabled[object_type] = False

    def is_enabled(self, object_type: str) -> bool:
        with self._lock:
            return self._enabled.get(object_type, False)

    def record(self, log: ObjectChangeLog) -> ObjectChangeLog | None:
        """记录变更。如果该 OT 未启用追踪则跳过。"""
        with self._lock:
            if not self._enabled.get(log.object_type, False):
                return None
            self._logs.append(log)
            return log

    def record_force(self, log: ObjectChangeLog) -> ObjectChangeLog:
        """强制记录变更（忽略开关）。"""
        with self._lock:
            self._logs.append(log)
            return log

    def query(
        self,
        *,
        object_type: str | None = None,
        object_id: str | None = None,
        field: str | None = None,
        author: str | None = None,
        operation: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[ObjectChangeLog]:
        with self._lock:
            logs = list(self._logs)
        result: list[ObjectChangeLog] = []
        for log in logs:
            if object_type and log.object_type != object_type:
                continue
            if object_id and log.object_id != object_id:
                continue
            if field and log.field != field:
                continue
            if author and log.author != author:
                continue
            if operation and log.operation != operation:
                continue
            if since and log.timestamp < since:
                continue
            if until and log.timestamp > until:
                continue
            result.append(log)
        return result[:limit]

    def get_timeline(self, object_type: str, object_id: str) -> list[ObjectChangeLog]:
        """获取指定对象的完整变更时间线。"""
        return self.query(object_type=object_type, object_id=object_id, limit=10000)

    def reset(self) -> None:
        with self._lock:
            self._logs.clear()
            self._enabled.clear()


# ─────────────── 单例 ───────────────

_conflict_engine: ConflictEngine | None = None
_migration_engine: MigrationEngine | None = None
_changelog_engine: ChangeLogEngine | None = None
_lock = threading.Lock()


def get_conflict_engine() -> ConflictEngine:
    global _conflict_engine
    if _conflict_engine is None:
        with _lock:
            if _conflict_engine is None:
                _conflict_engine = ConflictEngine()
    return _conflict_engine


def get_migration_engine() -> MigrationEngine:
    global _migration_engine
    if _migration_engine is None:
        with _lock:
            if _migration_engine is None:
                _migration_engine = MigrationEngine()
    return _migration_engine


def get_changelog_engine() -> ChangeLogEngine:
    global _changelog_engine
    if _changelog_engine is None:
        with _lock:
            if _changelog_engine is None:
                _changelog_engine = ChangeLogEngine()
    return _changelog_engine
