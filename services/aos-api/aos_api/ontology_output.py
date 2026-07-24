"""W2-3 · Ontology 对象类型输出。

从 Pipeline 输出的 dataset 定义 Ontology 对象类型，设置主键/标题字段，
可在 Object Explorer 查看。连接 Pipeline Builder 与 Ontology 的关键桥梁。

详见 docs/palantier/20_tech/220tech_w2-wave-plan.md 第一批。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

FieldType = str  # "string" | "number" | "boolean" | "date" | "geopoint" | "media_reference"


class ObjectField(BaseModel):
    name: str
    type: FieldType = "string"
    nullable: bool = True


class ObjectTypeDefinition(BaseModel):
    id: str = Field(default_factory=lambda: "otd-" + uuid.uuid4().hex[:10])
    name: str
    display_name: str = ""
    primary_key: str
    title_field: str = ""
    fields: list[ObjectField] = Field(default_factory=list)
    source_dataset_rid: str = ""
    source_pipeline_id: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OntologyOutputError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class OntologyOutputStore:
    def __init__(self) -> None:
        self._defs: dict[str, ObjectTypeDefinition] = {}

    def define(self, otd: ObjectTypeDefinition) -> ObjectTypeDefinition:
        self._validate(otd)
        self._defs[otd.id] = otd
        return otd

    def _validate(self, otd: ObjectTypeDefinition) -> None:
        if not otd.name:
            raise OntologyOutputError("MISSING_NAME", "对象类型名称不能为空")
        pk_found = any(f.name == otd.primary_key for f in otd.fields) if otd.fields else False
        if otd.fields and not pk_found:
            raise OntologyOutputError(
                "PK_NOT_IN_FIELDS",
                f"主键字段 '{otd.primary_key}' 不在字段列表中",
            )
        for existing in self._defs.values():
            if existing.name == otd.name and existing.id != otd.id:
                raise OntologyOutputError(
                    "NAME_DUPLICATE", f"对象类型名 '{otd.name}' 已存在")

    def get(self, otd_id: str) -> ObjectTypeDefinition | None:
        return self._defs.get(otd_id)

    def get_by_name(self, name: str) -> ObjectTypeDefinition | None:
        for otd in self._defs.values():
            if otd.name == name:
                return otd
        return None

    def list_all(self) -> list[ObjectTypeDefinition]:
        return list(self._defs.values())

    def delete(self, otd_id: str) -> bool:
        return self._defs.pop(otd_id, None) is not None

    def infer_fields(self, rows: list[dict[str, Any]]) -> list[ObjectField]:
        if not rows:
            return []
        columns = list(rows[0].keys())
        result: list[ObjectField] = []
        for col in columns:
            sample = rows[0].get(col)
            result.append(ObjectField(
                name=col,
                type=_infer_type(sample),
                nullable=any(r.get(col) is None for r in rows),
            ))
        return result

    def preview_objects(
        self, otd_id: str, rows: list[dict[str, Any]], limit: int = 100
    ) -> list[dict[str, Any]]:
        otd = self._defs.get(otd_id)
        if otd is None:
            raise OntologyOutputError("NOT_FOUND", f"对象类型定义 {otd_id} 不存在")
        objects: list[dict[str, Any]] = []
        for row in rows[:limit]:
            pk_val = row.get(otd.primary_key)
            if pk_val is None:
                continue
            title_val = row.get(otd.title_field) if otd.title_field else ""
            objects.append({
                "object_id": str(pk_val),
                "object_type": otd.name,
                "title": str(title_val) if title_val else str(pk_val),
                "properties": {f.name: row.get(f.name) for f in otd.fields},
            })
        return objects


def _infer_type(val: Any) -> str:
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "number"
    if isinstance(val, float):
        return "number"
    return "string"


_store = OntologyOutputStore()


def get_store() -> OntologyOutputStore:
    return _store
