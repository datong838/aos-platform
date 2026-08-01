"""Strict public contracts and safety limits for canonical AIP Logic dry-runs."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.aip_logic_graph_models import LogicBlockKind
from aos_api.public_contracts import redact_sensitive

MAX_INPUT_BYTES = 256 * 1024
MAX_JSON_DEPTH = 16
MAX_COLLECTION_ITEMS = 2_000
MAX_STRING_LENGTH = 32_768
MAX_KEY_LENGTH = 256
MAX_SAFE_OUTPUT_BYTES = 128 * 1024
MAX_TOTAL_CONTEXT_BYTES = 1024 * 1024
MAX_TOTAL_RESULT_BYTES = 2 * 1024 * 1024
REDACTED = "[REDACTED]"
_FORBIDDEN_RESULT_KEYS = re.compile(
    r"^(?:cot|reasoning|chain_of_thought)$", re.IGNORECASE
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _walk_json(value: Any, *, depth: int = 1) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError("JSON depth limit exceeded")
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON number must be finite")
        return
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise ValueError("JSON string length limit exceeded")
        return
    if isinstance(value, list):
        if len(value) > MAX_COLLECTION_ITEMS:
            raise ValueError("JSON collection length limit exceeded")
        for item in value:
            _walk_json(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_COLLECTION_ITEMS:
            raise ValueError("JSON collection length limit exceeded")
        for key, child in value.items():
            if not isinstance(key, str) or not key or len(key) > MAX_KEY_LENGTH:
                raise ValueError("JSON object key is invalid")
            if _FORBIDDEN_RESULT_KEYS.match(key):
                raise ValueError("private reasoning fields are forbidden")
            _walk_json(child, depth=depth + 1)
        return
    raise ValueError("value must contain JSON-compatible types only")


def validate_json_value(value: Any, *, max_bytes: int = MAX_SAFE_OUTPUT_BYTES) -> Any:
    _walk_json(value)
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError("JSON byte limit exceeded")
    return value


def sanitize_runtime_value(
    value: Any, *, max_bytes: int = MAX_SAFE_OUTPUT_BYTES
) -> tuple[Any, bool]:
    """Apply the shared recursive redactor and a deterministic byte cap."""
    safe = redact_sensitive(value)
    _walk_json(safe)
    encoded = json.dumps(
        safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError("sanitized JSON byte limit exceeded")
    return safe, False


class LogicDryRunRequest(_StrictModel):
    expected_revision: int = Field(ge=1)
    dry_run: Literal[True]
    expected_graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    inputs: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=160)

    @field_validator("dry_run", mode="before")
    @classmethod
    def _literal_boolean_true(cls, value: Any) -> bool:
        if type(value) is not bool or value is not True:
            raise ValueError("dry_run must be the boolean literal true")
        return value

    @field_validator("inputs")
    @classmethod
    def _validate_inputs(cls, value: dict[str, Any]) -> dict[str, Any]:
        validate_json_value(value, max_bytes=MAX_INPUT_BYTES)
        return value

    @field_validator("idempotency_key")
    @classmethod
    def _normalize_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key must not be blank")
        return normalized


class LogicRunError(_StrictModel):
    code: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=500)
    node_id: str | None = Field(default=None, max_length=160)
    reason: str | None = Field(default=None, max_length=160)


class LogicTokenUsage(_StrictModel):
    model: str = Field(min_length=1, max_length=240)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _consistent_total(self) -> LogicTokenUsage:
        if self.input_tokens + self.output_tokens != self.total_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        return self


class LogicToolCall(_StrictModel):
    tool: str = Field(min_length=1, max_length=240)
    adapter: str = Field(min_length=1, max_length=240)
    read_only: Literal[True]
    dry_run_safe: Literal[True]


class LogicProposedEdit(_StrictModel):
    action: str = Field(min_length=1, max_length=240)
    object_id: str = Field(min_length=1, max_length=240)
    field: str = Field(min_length=1, max_length=240)
    value: Any
    source_node_id: str = Field(min_length=1, max_length=160)
    applied: Literal[False] = False

    @field_validator("value")
    @classmethod
    def _safe_value(cls, value: Any) -> Any:
        return validate_json_value(value)


class LogicNodeResult(_StrictModel):
    node_id: str
    kind: LogicBlockKind
    status: Literal["executed", "skipped", "failed", "canceled"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)
    summary: str = Field(max_length=500)
    output: Any | None = None
    usage: LogicTokenUsage | None = None
    tool_call: LogicToolCall | None = None
    selected_branch_path: str | None = None
    proposed_edits: list[LogicProposedEdit] = Field(default_factory=list)
    error: LogicRunError | None = None
    truncated: bool = False

    @field_validator("output")
    @classmethod
    def _safe_output(cls, value: Any | None) -> Any | None:
        return validate_json_value(value) if value is not None else None


class LogicDryRun(_StrictModel):
    run_id: str
    graph_id: str
    mode: Literal["dry_run"] = "dry_run"
    status: Literal["succeeded", "failed"]
    evaluated_revision: int = Field(ge=1)
    graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    production_written: Literal[False] = False
    started_at: datetime
    finished_at: datetime
    elapsed_ms: int = Field(ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    node_results: list[LogicNodeResult] = Field(default_factory=list)
    proposed_edits: list[LogicProposedEdit] = Field(default_factory=list)
    error: LogicRunError | None = None


class LogicNodeCounts(_StrictModel):
    executed: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    canceled: int = Field(default=0, ge=0)


class LogicRunSummary(_StrictModel):
    run_id: str
    graph_id: str
    mode: Literal["dry_run"] = "dry_run"
    status: Literal["succeeded", "failed"]
    evaluated_revision: int
    graph_hash: str
    production_written: Literal[False] = False
    started_at: datetime
    finished_at: datetime
    elapsed_ms: int
    total_tokens: int | None = None
    node_counts: LogicNodeCounts
    error_code: str | None = None


class LogicRunListResponse(_StrictModel):
    items: list[LogicRunSummary] = Field(default_factory=list)
    count: int = Field(ge=0)
    next_cursor: str | None = None
