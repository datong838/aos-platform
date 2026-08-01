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
MAX_SAFE_INTEGER = (1 << 53) - 1
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
    expected_revision: int = Field(ge=1, le=MAX_SAFE_INTEGER)
    dry_run: Literal[True]
    expected_graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    inputs: dict[str, Any]
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
    input_tokens: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    output_tokens: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    total_tokens: int = Field(ge=0, le=MAX_SAFE_INTEGER)

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
    node_id: str = Field(min_length=1, max_length=160)
    kind: LogicBlockKind
    status: Literal["executed", "skipped", "failed", "canceled"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    elapsed_ms: int | None = Field(default=None, ge=0, le=MAX_SAFE_INTEGER)
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

    @model_validator(mode="after")
    def _cross_field_truth(self) -> LogicNodeResult:
        if self.error is not None and self.error.node_id != self.node_id:
            raise ValueError("node error must belong to its node result")
        if self.status == "executed" and self.error is not None:
            raise ValueError("executed node must not contain an error")
        if self.status == "failed" and self.error is None:
            raise ValueError("failed node must contain an error")
        if self.status in {"skipped", "canceled"} and not (
            self.error and self.error.reason
        ):
            raise ValueError("idle node must contain a machine-readable reason")
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("node finished_at must not precede started_at")
        if any(edit.source_node_id != self.node_id for edit in self.proposed_edits):
            raise ValueError("node proposed edit must belong to its source node")
        return self


class LogicDryRun(_StrictModel):
    run_id: str = Field(min_length=1, max_length=160)
    graph_id: str = Field(min_length=1, max_length=160)
    mode: Literal["dry_run"] = "dry_run"
    status: Literal["succeeded", "failed"]
    evaluated_revision: int = Field(ge=1, le=MAX_SAFE_INTEGER)
    graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    production_written: Literal[False] = False
    started_at: datetime
    finished_at: datetime
    elapsed_ms: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    total_tokens: int | None = Field(default=None, ge=0, le=MAX_SAFE_INTEGER)
    node_results: list[LogicNodeResult] = Field(default_factory=list)
    proposed_edits: list[LogicProposedEdit] = Field(default_factory=list)
    error: LogicRunError | None = None

    @model_validator(mode="after")
    def _cross_field_truth(self) -> LogicDryRun:
        if self.finished_at < self.started_at:
            raise ValueError("run finished_at must not precede started_at")
        node_ids = [node.node_id for node in self.node_results]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("run node results must have unique node ids")
        failed_ids = {
            node.node_id for node in self.node_results if node.status == "failed"
        }
        if self.status == "succeeded":
            if self.error is not None:
                raise ValueError("succeeded run must not contain an error")
            if any(
                node.status not in {"executed", "skipped"} for node in self.node_results
            ):
                raise ValueError("succeeded run contains a failed or canceled node")
        else:
            if self.error is None:
                raise ValueError("failed run must contain an error")
            if not failed_ids:
                raise ValueError("failed run must contain at least one failed node")
            if self.error.node_id not in failed_ids:
                raise ValueError("run error must identify a failed node")
        usage_totals = [
            node.usage.total_tokens
            for node in self.node_results
            if node.usage is not None
        ]
        expected_tokens = sum(usage_totals) if usage_totals else None
        if self.total_tokens != expected_tokens:
            raise ValueError("run total_tokens must equal node usage totals")
        allowed_nodes = set(node_ids)
        edits = [
            *self.proposed_edits,
            *[edit for node in self.node_results for edit in node.proposed_edits],
        ]
        if any(edit.source_node_id not in allowed_nodes for edit in edits):
            raise ValueError("run proposed edit source must belong to a result node")
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_TOTAL_RESULT_BYTES:
            raise ValueError("dry-run result byte limit exceeded")
        return self


class LogicNodeCounts(_StrictModel):
    executed: int = Field(default=0, ge=0, le=MAX_SAFE_INTEGER)
    skipped: int = Field(default=0, ge=0, le=MAX_SAFE_INTEGER)
    failed: int = Field(default=0, ge=0, le=MAX_SAFE_INTEGER)
    canceled: int = Field(default=0, ge=0, le=MAX_SAFE_INTEGER)


class LogicRunSummary(_StrictModel):
    run_id: str = Field(min_length=1, max_length=160)
    graph_id: str = Field(min_length=1, max_length=160)
    mode: Literal["dry_run"] = "dry_run"
    status: Literal["succeeded", "failed"]
    evaluated_revision: int = Field(ge=1, le=MAX_SAFE_INTEGER)
    graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    production_written: Literal[False] = False
    started_at: datetime
    finished_at: datetime
    elapsed_ms: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    total_tokens: int | None = Field(default=None, ge=0, le=MAX_SAFE_INTEGER)
    node_counts: LogicNodeCounts
    error_code: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def _cross_field_truth(self) -> LogicRunSummary:
        if self.finished_at < self.started_at:
            raise ValueError("summary finished_at must not precede started_at")
        if self.status == "succeeded":
            if (
                self.node_counts.failed != 0
                or self.node_counts.canceled != 0
                or self.error_code is not None
            ):
                raise ValueError("succeeded summary contains failure evidence")
        elif self.node_counts.failed < 1 or self.error_code is None:
            raise ValueError("failed summary lacks failed node evidence")
        return self


class LogicRunListResponse(_StrictModel):
    items: list[LogicRunSummary] = Field(default_factory=list)
    count: int = Field(ge=0)
    next_cursor: str | None = None
