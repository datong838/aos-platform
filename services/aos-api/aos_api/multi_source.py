"""W2-20 · Pipeline 多数据源支持。

扩展 Pipeline Builder 支持多个输入数据源 + 多表 Join 链（订单→商品→买家）。
复用 W1-8 transform_ops 的 Join 算子。

详见 docs/palantier/20_tech/220tech_w2-wave-plan.md 第一批。
"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from .transform_ops import apply_transform


class DataSource(BaseModel):
    id: str
    name: str = ""
    rows: list[dict[str, Any]] = Field(default_factory=list)


class JoinConfig(BaseModel):
    left_source_id: str
    right_source_id: str
    left_key: str
    right_key: str
    join_type: str = "inner"


class MultiSourcePipeline(BaseModel):
    id: str = Field(default_factory=lambda: "msp-" + uuid.uuid4().hex[:10])
    name: str
    sources: dict[str, DataSource] = Field(default_factory=dict)
    joins: list[JoinConfig] = Field(default_factory=list)
    output: list[dict[str, Any]] = Field(default_factory=list)


class MultiSourceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class MultiSourceEngine:
    def __init__(self) -> None:
        self._pipelines: dict[str, MultiSourcePipeline] = {}

    def create(self, name: str) -> MultiSourcePipeline:
        msp = MultiSourcePipeline(name=name)
        self._pipelines[msp.id] = msp
        return msp

    def get(self, msp_id: str) -> MultiSourcePipeline | None:
        return self._pipelines.get(msp_id)

    def add_source(self, msp_id: str, source: DataSource) -> DataSource:
        msp = self._require(msp_id)
        msp.sources[source.id] = source
        return source

    def add_join(self, msp_id: str, join: JoinConfig) -> JoinConfig:
        msp = self._require(msp_id)
        if join.left_source_id not in msp.sources:
            raise MultiSourceError("SOURCE_NOT_FOUND", f"左数据源 {join.left_source_id} 不存在")
        if join.right_source_id not in msp.sources:
            raise MultiSourceError("SOURCE_NOT_FOUND", f"右数据源 {join.right_source_id} 不存在")
        msp.joins.append(join)
        return join

    def execute(self, msp_id: str) -> list[dict[str, Any]]:
        msp = self._require(msp_id)
        if not msp.joins:
            if len(msp.sources) == 1:
                result = list(list(msp.sources.values())[0].rows)
            else:
                result = []
                for src in msp.sources.values():
                    result.extend(src.rows)
            msp.output = result
            return result

        current_source_id = msp.joins[0].left_source_id
        current_rows = list(msp.sources[current_source_id].rows)

        for join in msp.joins:
            right_rows = list(msp.sources[join.right_source_id].rows)
            current_rows = apply_transform("join", current_rows, {
                "right": right_rows,
                "left_key": join.left_key,
                "right_key": join.right_key,
                "how": join.join_type,
            })

        msp.output = current_rows
        return current_rows

    def _require(self, msp_id: str) -> MultiSourcePipeline:
        msp = self._pipelines.get(msp_id)
        if msp is None:
            raise MultiSourceError("NOT_FOUND", f"多源管道 {msp_id} 不存在")
        return msp


_engine = MultiSourceEngine()


def get_engine() -> MultiSourceEngine:
    return _engine
