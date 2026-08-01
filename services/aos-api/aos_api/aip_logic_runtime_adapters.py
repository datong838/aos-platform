"""Explicit fail-closed capability registry for AIP Logic dry-run execution."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aos_api.aip_logic_dry_run_models import LogicTokenUsage, validate_json_value


class LogicAdapterError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.safe_message = message
        super().__init__(message)


@dataclass(frozen=True)
class AdapterExecutionContext:
    """Cooperative deadline contract; adapters must checkpoint before I/O and loops."""

    deadline: float
    monotonic: Callable[[], float]

    def checkpoint(self) -> None:
        if self.monotonic() >= self.deadline:
            raise LogicAdapterError(
                "ADAPTER_TIMEOUT", "dry-run adapter time budget exceeded"
            )


@dataclass(frozen=True)
class LLMAdapterResult:
    output: str
    usage: LogicTokenUsage


@dataclass(frozen=True)
class ToolAdapterResult:
    output: Any


@dataclass(frozen=True)
class ExecuteAdapterResult:
    preview: Any


@dataclass(frozen=True)
class _ToolRegistration:
    name: str
    adapter_name: str
    invoke: Callable[[dict[str, Any], AdapterExecutionContext], ToolAdapterResult]
    read_only: bool
    dry_run_safe: bool


class RuntimeAdapterRegistry:
    """No implicit global adapters: every external capability must be injected."""

    def __init__(self, *, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._monotonic = monotonic
        self._llms: dict[
            str, tuple[str, Callable[[str, AdapterExecutionContext], LLMAdapterResult]]
        ] = {}
        self._tools: dict[str, _ToolRegistration] = {}
        self._execute: dict[
            str,
            tuple[
                str,
                Callable[
                    [dict[str, Any], AdapterExecutionContext], ExecuteAdapterResult
                ],
            ],
        ] = {}

    def register_llm(
        self,
        model: str,
        invoke: Callable[[str, AdapterExecutionContext], LLMAdapterResult],
        *,
        adapter_name: str,
    ) -> None:
        self._llms[model] = (adapter_name, invoke)

    def invoke_llm(
        self, model: str, prompt: str, *, timeout_seconds: float
    ) -> tuple[str, LLMAdapterResult]:
        registration = self._llms.get(model)
        if registration is None:
            raise LogicAdapterError(
                "LLM_ADAPTER_UNAVAILABLE", "approved dry-run LLM adapter unavailable"
            )
        adapter_name, invoke = registration
        context = AdapterExecutionContext(
            self._monotonic() + timeout_seconds, self._monotonic
        )
        try:
            context.checkpoint()
            result = invoke(prompt, context)
            context.checkpoint()
        except LogicAdapterError:
            raise
        except Exception as exc:
            raise LogicAdapterError(
                "LLM_ADAPTER_FAILED", "dry-run LLM adapter failed"
            ) from exc
        if not isinstance(result, LLMAdapterResult) or result.usage.model != model:
            raise LogicAdapterError(
                "LLM_USAGE_INVALID", "dry-run LLM adapter returned invalid usage"
            )
        return adapter_name, result

    def register_tool(
        self,
        tool: str,
        invoke: Callable[[dict[str, Any], AdapterExecutionContext], ToolAdapterResult],
        *,
        adapter_name: str,
        read_only: bool,
        dry_run_safe: bool,
    ) -> None:
        self._tools[tool] = _ToolRegistration(
            tool, adapter_name, invoke, read_only, dry_run_safe
        )

    def invoke_tool(
        self, tool: str, arguments: dict[str, Any], *, timeout_seconds: float
    ) -> tuple[_ToolRegistration, ToolAdapterResult]:
        registration = self._tools.get(tool)
        if registration is None:
            raise LogicAdapterError(
                "TOOL_ADAPTER_UNAVAILABLE", "approved dry-run tool adapter unavailable"
            )
        if not registration.read_only or not registration.dry_run_safe:
            raise LogicAdapterError(
                "TOOL_NOT_DRY_RUN_SAFE", "tool is not read-only and dry-run safe"
            )
        validate_json_value(arguments)
        context = AdapterExecutionContext(
            self._monotonic() + timeout_seconds, self._monotonic
        )
        try:
            context.checkpoint()
            result = registration.invoke(arguments, context)
            context.checkpoint()
        except LogicAdapterError:
            raise
        except Exception as exc:
            raise LogicAdapterError(
                "TOOL_ADAPTER_FAILED", "dry-run tool adapter failed"
            ) from exc
        if not isinstance(result, ToolAdapterResult):
            raise LogicAdapterError(
                "TOOL_RESULT_INVALID", "dry-run tool adapter returned an invalid result"
            )
        validate_json_value(result.output)
        return registration, result

    def register_execute(
        self,
        target: str,
        invoke: Callable[
            [dict[str, Any], AdapterExecutionContext], ExecuteAdapterResult
        ],
        *,
        adapter_name: str,
    ) -> None:
        self._execute[target] = (adapter_name, invoke)

    def preview_execute(
        self, target: str, request: dict[str, Any], *, timeout_seconds: float
    ) -> tuple[str, ExecuteAdapterResult]:
        registration = self._execute.get(target)
        if registration is None:
            raise LogicAdapterError(
                "EXECUTE_ADAPTER_UNAVAILABLE",
                "approved sandbox execute adapter unavailable",
            )
        adapter_name, invoke = registration
        validate_json_value(request)
        context = AdapterExecutionContext(
            self._monotonic() + timeout_seconds, self._monotonic
        )
        try:
            context.checkpoint()
            result = invoke(request, context)
            context.checkpoint()
        except LogicAdapterError:
            raise
        except Exception as exc:
            raise LogicAdapterError(
                "EXECUTE_ADAPTER_FAILED", "sandbox execute adapter failed"
            ) from exc
        if not isinstance(result, ExecuteAdapterResult):
            raise LogicAdapterError(
                "EXECUTE_RESULT_INVALID",
                "sandbox execute adapter returned an invalid preview",
            )
        validate_json_value(result.preview)
        return adapter_name, result
