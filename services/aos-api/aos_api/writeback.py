"""W1-6 · Action 写回协议（L1 Write-back Dataset）。

Ontology 写回闭环的核心：Action 执行时不直接改底层 dataset，
而是写入 L1 覆盖层（WritebackLayer），支持软删除、乐观锁、事务。

详见 docs/palantier/20_tech/220tech_writeback.md。
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


MAX_ENTRIES = 10_000


class WritebackOp(BaseModel):
    op: Literal["upsert", "soft_delete", "undelete"] = "upsert"
    pk: str
    row: dict[str, Any] = Field(default_factory=dict)


class WritebackEntry(BaseModel):
    pk: str
    row: dict[str, Any] = Field(default_factory=dict)
    deleted: bool = False
    version: int = 1
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class WritebackLayer(BaseModel):
    dataset_rid: str
    entries: dict[str, WritebackEntry] = Field(default_factory=dict)
    status: Literal["open", "committed", "rolled_back"] = "open"
    opened_at: str = Field(default_factory=_now)
    committed_at: str | None = None
    workshop_module: str | None = None
    workshop_bound_at: str | None = None


class WritebackError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _new_txn_id() -> str:
    return "wb-" + uuid.uuid4().hex[:12]


class WritebackStore:
    def __init__(self) -> None:
        self._txns: dict[str, WritebackLayer] = {}
        self._by_dataset: dict[str, str] = {}
        self._lock = threading.Lock()

    def begin(self, dataset_rid: str) -> str:
        if not dataset_rid:
            raise WritebackError("BAD_DATASET", "dataset_rid 不能为空")
        with self._lock:
            existing_txn = self._by_dataset.get(dataset_rid)
            if existing_txn and self._txns.get(existing_txn, None) and self._txns[existing_txn].status == "open":
                raise WritebackError(
                    "TXN_OPEN",
                    f"dataset {dataset_rid!r} 已有进行中的事务 {existing_txn}",
                )
            txn_id = _new_txn_id()
            layer = WritebackLayer(dataset_rid=dataset_rid)
            self._txns[txn_id] = layer
            self._by_dataset[dataset_rid] = txn_id
            return txn_id

    def apply(self, txn_id: str, ops: list[WritebackOp]) -> WritebackLayer:
        with self._lock:
            layer = self._require_open(txn_id)
            for op in ops:
                self._apply_one(layer, op)
            return layer

    def _apply_one(self, layer: WritebackLayer, op: WritebackOp) -> None:
        if len(layer.entries) >= MAX_ENTRIES:
            raise WritebackError("LAYER_FULL", f"entries 已达上限 {MAX_ENTRIES}")
        existing = layer.entries.get(op.pk)
        now = _now()
        if op.op == "upsert":
            if existing is None:
                layer.entries[op.pk] = WritebackEntry(
                    pk=op.pk, row=dict(op.row), deleted=False, version=1,
                    created_at=now, updated_at=now,
                )
            else:
                merged = {**existing.row, **op.row}
                layer.entries[op.pk] = existing.model_copy(update={
                    "row": merged, "deleted": False,
                    "version": existing.version + 1, "updated_at": now,
                })
        elif op.op == "soft_delete":
            if existing is None:
                layer.entries[op.pk] = WritebackEntry(
                    pk=op.pk, row={}, deleted=True, version=1,
                    created_at=now, updated_at=now,
                )
            else:
                layer.entries[op.pk] = existing.model_copy(update={
                    "deleted": True, "version": existing.version + 1, "updated_at": now,
                })
        elif op.op == "undelete":
            if existing is None:
                raise WritebackError("ENTRY_NOT_FOUND", f"pk {op.pk!r} 不存在，无法 undelete")
            layer.entries[op.pk] = existing.model_copy(update={
                "deleted": False, "version": existing.version + 1, "updated_at": now,
            })
        else:
            raise WritebackError("BAD_OP", f"未知 op {op.op!r}")

    def commit(self, txn_id: str) -> WritebackLayer:
        with self._lock:
            layer = self._require_open(txn_id)
            layer.status = "committed"
            layer.committed_at = _now()
            return layer

    def rollback(self, txn_id: str) -> WritebackLayer:
        with self._lock:
            layer = self._txns.get(txn_id)
            if layer is None:
                raise WritebackError("NOT_FOUND", f"事务 {txn_id!r} 不存在")
            if layer.status != "open":
                raise WritebackError("TXN_CLOSED", f"事务已 {layer.status}，无法 rollback")
            layer.status = "rolled_back"
            return layer

    def get_layer(self, dataset_rid: str) -> WritebackLayer | None:
        txn_id = self._by_dataset.get(dataset_rid)
        if txn_id is None:
            return None
        return self._txns.get(txn_id)

    def get_txn(self, txn_id: str) -> WritebackLayer | None:
        return self._txns.get(txn_id)

    def bind_workshop(self, dataset_rid: str, module_id: str) -> WritebackLayer:
        if not module_id:
            raise WritebackError("BAD_MODULE", "module_id 不能为空")
        with self._lock:
            layer = self.get_layer(dataset_rid)
            if layer is None:
                raise WritebackError("NOT_FOUND", f"dataset {dataset_rid!r} 无 L1 覆盖层")
            layer.workshop_module = module_id
            layer.workshop_bound_at = _now()
            return layer

    def unbind_workshop(self, dataset_rid: str) -> WritebackLayer:
        with self._lock:
            layer = self.get_layer(dataset_rid)
            if layer is None:
                raise WritebackError("NOT_FOUND", f"dataset {dataset_rid!r} 无 L1 覆盖层")
            layer.workshop_module = None
            layer.workshop_bound_at = None
            return layer

    def list_by_workshop(self, module_id: str) -> list[WritebackLayer]:
        with self._lock:
            return [
                layer for layer in self._txns.values()
                if layer.workshop_module == module_id
            ]

    def view(self, dataset_rid: str, base_rows: list[dict[str, Any]], pk_field: str) -> list[dict[str, Any]]:
        if not pk_field:
            raise WritebackError("BAD_PK", "pk_field 不能为空")
        base_map: dict[str, dict[str, Any]] = {}
        for r in base_rows:
            if pk_field in r:
                base_map[str(r[pk_field])] = dict(r)
        layer = self.get_layer(dataset_rid)
        if layer is None or layer.status != "committed":
            return list(base_map.values())
        for pk, entry in layer.entries.items():
            if entry.deleted:
                base_map.pop(pk, None)
            else:
                merged = {**base_map.get(pk, {}), **entry.row}
                base_map[pk] = merged
        return list(base_map.values())

    def _require_open(self, txn_id: str) -> WritebackLayer:
        layer = self._txns.get(txn_id)
        if layer is None:
            raise WritebackError("NOT_FOUND", f"事务 {txn_id!r} 不存在")
        if layer.status != "open":
            raise WritebackError("TXN_CLOSED", f"事务已 {layer.status}，无法操作")
        return layer


_store = WritebackStore()


def get_store() -> WritebackStore:
    return _store
