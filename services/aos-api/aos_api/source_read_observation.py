"""Actual connector read intervals; not persisted source or freshness authority."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, StrictInt, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


def _typed(value: Any) -> Any:
    if value is None:
        return ["null"]
    if type(value) in {str, bool, int}:
        return [type(value).__name__, value]
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite observation value")
        return ["float", value.hex()]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("nonfinite observation decimal")
        return ["decimal", str(value)]
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("observation datetime requires timezone")
        return ["datetime", value.astimezone(UTC).isoformat(timespec="microseconds")]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("observation keys must be strings")
        return ["dict", [[key, _typed(value[key])] for key in sorted(value)]]
    if type(value) in {list, tuple}:
        return ["list", [_typed(item) for item in value]]
    raise TypeError("unsupported observation value")


def observed_rows_hash(rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> str:
    if type(rows) not in {list, tuple} or any(type(row) is not dict for row in rows):
        raise ValueError("observation rows must be dictionaries")
    body = json.dumps(_typed(rows), ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


class _ObservationTenant(TenantContext):
    model_config = ConfigDict(frozen=True)


class SourceReadObservation(AipContractModel):
    model_config = ConfigDict(frozen=True)
    schema_version: Literal["aos.source-read-observation/v1"] = "aos.source-read-observation/v1"
    tenant: _ObservationTenant
    source_id: str = Field(min_length=1, max_length=240)
    spec_id: Literal["niushop.product-observation/v1"]
    site_id: StrictInt = Field(gt=0)
    read_started_at: datetime
    read_finished_at: datetime
    fetched_count: StrictInt = Field(ge=0, le=100)
    excluded_count: StrictInt = Field(ge=0, le=100)
    retained_count: StrictInt = Field(ge=0, le=100)
    rows_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cleaning_version: Literal["niushop.product-public-fields/v1"] = "niushop.product-public-fields/v1"
    source_configuration_ref: None = None
    upstream_snapshot_at: None = None

    @field_validator("source_id")
    @classmethod
    def _source(cls, value: str) -> str:
        if value != value.strip() or not value.strip():
            raise ValueError("canonical source identity required")
        return value

    @field_validator("read_started_at", "read_finished_at")
    @classmethod
    def _time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observation interval requires timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _interval_and_counts(self) -> Self:
        if self.read_finished_at < self.read_started_at:
            raise ValueError("observation clock moved backwards")
        if self.fetched_count != self.excluded_count + self.retained_count:
            raise ValueError("observation counts do not partition fetched rows")
        return self

    def verify_rows(self, rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> None:
        item = SourceReadObservation.model_validate(self.model_dump())
        if len(rows) != item.retained_count or observed_rows_hash(rows) != item.rows_hash:
            raise ValueError("observation rows drifted")
