"""W2-#24 / W2-#16 / W2-#17 · Data Connection 事务类型 + 写入模式 + 事务状态机。

支持四种数据写入模式：
  - DEFAULT: 默认模式（等同 append）
  - APPEND:  追加模式，保留存量 + 追加增量
  - SNAPSHOT: 快照模式，全量替换存量数据
  - UPDATE:  更新模式，按主键匹配 upsert

事务状态机（W2-#17）：
  OPEN → COMMITTED（提交，应用 write_mode 合并）
  OPEN → ABORTED  （中止，丢弃暂存数据）
  COMMITTED / ABORTED 不可逆

集成 connector_runtime 的 ingest 操作，write_mode 作为可选参数传入。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransactionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ── WriteMode（W2-#16 增强）──

WRITE_MODE_DEFAULT = "default"
WRITE_MODE_APPEND = "append"
WRITE_MODE_SNAPSHOT = "snapshot"
WRITE_MODE_UPDATE = "update"

ALL_WRITE_MODES = {WRITE_MODE_DEFAULT, WRITE_MODE_APPEND, WRITE_MODE_SNAPSHOT, WRITE_MODE_UPDATE}


def resolve_write_mode(raw: str | None) -> str:
    """标准化 write_mode 参数，默认 default。"""
    if raw is None:
        return WRITE_MODE_DEFAULT
    mode = raw.strip().lower()
    if mode not in ALL_WRITE_MODES:
        raise TransactionError(
            "UNKNOWN_WRITE_MODE",
            f"未知写入模式 {raw!r}，可用：{sorted(ALL_WRITE_MODES)}",
        )
    return mode


def apply_write_mode(
    existing_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    mode: str,
    primary_key: str = "id",
) -> list[dict[str, Any]]:
    """根据写入模式合并存量与增量数据。

    Args:
        existing_rows: 当前数据源中的存量数据
        new_rows: 本次摄取的新数据
        mode: write_mode（append/snapshot/update）
        primary_key: 主键字段名

    Returns:
        合并后的最终数据集

    Raises:
        TransactionError: 模式不合法
    """
    mode = resolve_write_mode(mode)

    # default 等同 append（W2-#16）
    if mode == WRITE_MODE_DEFAULT:
        mode = WRITE_MODE_APPEND

    if mode == WRITE_MODE_APPEND:
        # 追加模式：保留存量 + 追加增量（去重 by PK）
        existing_keys = {r.get(primary_key) for r in existing_rows if r.get(primary_key) is not None}
        dup_free = [r for r in new_rows if r.get(primary_key) not in existing_keys]
        return [*existing_rows, *dup_free]

    if mode == WRITE_MODE_SNAPSHOT:
        # 快照模式：全量替换
        return list(new_rows)

    if mode == WRITE_MODE_UPDATE:
        # Upsert 模式：按主键匹配
        existing_by_pk: dict[Any, dict[str, Any]] = {}
        for r in existing_rows:
            pk = r.get(primary_key)
            if pk is not None:
                existing_by_pk[pk] = r

        result_map: dict[Any, dict[str, Any]] = dict(existing_by_pk)
        for r in new_rows:
            pk = r.get(primary_key)
            if pk is not None:
                if pk in result_map:
                    # Merge: 新字段覆盖旧字段，旧字段保留
                    merged = {**result_map[pk], **r}
                    result_map[pk] = merged
                else:
                    result_map[pk] = dict(r)

        return list(result_map.values())

    # 不应该到达这里
    raise TransactionError("UNKNOWN_WRITE_MODE", f"无法处理的写入模式 {mode!r}")


def describe_write_modes() -> list[dict[str, Any]]:
    """返回所有写入模式说明。"""
    return [
        {
            "mode": WRITE_MODE_DEFAULT,
            "label": "默认（Default）",
            "description": "未指定写入模式时的默认行为，等同 Append。",
            "idempotent": True,
        },
        {
            "mode": WRITE_MODE_APPEND,
            "label": "追加（Append）",
            "description": "保留存量数据，追加新数据（去重 by PK）。适合日志/事件流场景。",
            "idempotent": True,
        },
        {
            "mode": WRITE_MODE_SNAPSHOT,
            "label": "快照（Snapshot）",
            "description": "全量替换存量数据为新数据。适合全量同步/维表场景。",
            "idempotent": True,
        },
        {
            "mode": WRITE_MODE_UPDATE,
            "label": "更新（Update）",
            "description": "按主键匹配 upsert，新字段覆盖旧字段，旧字段保留。适合增量更新场景。",
            "idempotent": True,
        },
    ]


# ── Transaction 状态机（W2-#17）──


class TransactionStatus(str, Enum):
    OPEN = "open"
    COMMITTED = "committed"
    ABORTED = "aborted"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DataTransaction(BaseModel):
    id: str = Field(default_factory=lambda: "txn-" + uuid.uuid4().hex[:10])
    dataset_rid: str
    write_mode: str = WRITE_MODE_DEFAULT
    status: TransactionStatus = TransactionStatus.OPEN
    opened_at: str = Field(default_factory=_now)
    committed_at: str | None = None
    aborted_at: str | None = None
    staged_rows: list[dict[str, Any]] = Field(default_factory=list)
    committed_rows: list[dict[str, Any]] = Field(default_factory=list)
    expectation_ids: list[str] = Field(default_factory=list)
    primary_key: str = "id"


class TransactionStore:
    """数据事务状态机存储（内存）。"""

    def __init__(self) -> None:
        self._txns: dict[str, DataTransaction] = {}
        self._datasets: dict[str, list[dict[str, Any]]] = {}

    def seed_dataset(self, rid: str, rows: list[dict[str, Any]]) -> None:
        self._datasets[rid] = [dict(r) for r in rows]

    def get_dataset(self, rid: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self._datasets.get(rid, [])]

    def begin(
        self,
        dataset_rid: str,
        write_mode: str = WRITE_MODE_DEFAULT,
        primary_key: str = "id",
        expectation_ids: list[str] | None = None,
    ) -> DataTransaction:
        mode = resolve_write_mode(write_mode)
        txn = DataTransaction(
            dataset_rid=dataset_rid,
            write_mode=mode,
            primary_key=primary_key,
            expectation_ids=expectation_ids or [],
        )
        self._txns[txn.id] = txn
        return txn

    def write(self, txn_id: str, rows: list[dict[str, Any]]) -> DataTransaction:
        txn = self._txns.get(txn_id)
        if txn is None:
            raise TransactionError("NOT_FOUND", f"事务 {txn_id!r} 不存在")
        if txn.status != TransactionStatus.OPEN:
            raise TransactionError(
                "TXN_NOT_OPEN",
                f"事务状态为 {txn.status.value}，无法写入（仅 OPEN 可写）",
            )
        txn.staged_rows.extend(rows)
        return txn

    def commit(self, txn_id: str) -> DataTransaction:
        txn = self._txns.get(txn_id)
        if txn is None:
            raise TransactionError("NOT_FOUND", f"事务 {txn_id!r} 不存在")
        if txn.status != TransactionStatus.OPEN:
            raise TransactionError(
                "TXN_NOT_OPEN",
                f"事务状态为 {txn.status.value}，无法提交（仅 OPEN 可提交）",
            )
        existing = self.get_dataset(txn.dataset_rid)
        merged = apply_write_mode(existing, txn.staged_rows, txn.write_mode, txn.primary_key)
        self._datasets[txn.dataset_rid] = merged
        txn.committed_rows = merged
        txn.status = TransactionStatus.COMMITTED
        txn.committed_at = _now()
        return txn

    def abort(self, txn_id: str) -> DataTransaction:
        txn = self._txns.get(txn_id)
        if txn is None:
            raise TransactionError("NOT_FOUND", f"事务 {txn_id!r} 不存在")
        if txn.status != TransactionStatus.OPEN:
            raise TransactionError(
                "TXN_NOT_OPEN",
                f"事务状态为 {txn.status.value}，无法中止（仅 OPEN 可中止）",
            )
        txn.staged_rows = []
        txn.status = TransactionStatus.ABORTED
        txn.aborted_at = _now()
        return txn

    def get(self, txn_id: str) -> DataTransaction | None:
        return self._txns.get(txn_id)

    def list(self, dataset_rid: str | None = None) -> list[DataTransaction]:
        if dataset_rid:
            return [t for t in self._txns.values() if t.dataset_rid == dataset_rid]
        return list(self._txns.values())


_store = TransactionStore()


def get_store() -> TransactionStore:
    return _store

