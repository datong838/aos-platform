"""Deterministic, fail-fast DAG executor for persisted AIP Logic dry-runs."""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from aos_api.aip_logic_dry_run_models import (
    MAX_TOTAL_CONTEXT_BYTES,
    MAX_TOTAL_RESULT_BYTES,
    LogicDryRun,
    LogicNodeResult,
    LogicProposedEdit,
    LogicRunError,
    LogicToolCall,
    sanitize_runtime_value,
    validate_json_value,
)
from aos_api.aip_logic_graph_models import (
    LogicGraphSnapshot,
    LogicGraphValidationError,
    ValidateLogicGraphRequest,
    compute_logic_graph_payload_hash,
    validate_logic_graph,
)
from aos_api.aip_logic_runtime_adapters import LogicAdapterError, RuntimeAdapterRegistry
from aos_api.function_engine import FunctionError, evaluate, parse

MAX_TOTAL_SECONDS = 30.0
MAX_NODE_SECONDS = 10.0
HANDOFF_ALLOWLIST = frozenset({"risk_agent", "draft_inbox", "webhook"})


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _InputConfig(_Config):
    schema: dict[str, Any] = Field(default_factory=dict)


class _VariableConfig(_Config):
    name: str = Field(min_length=1, max_length=160)
    expression: str = Field(min_length=1)


class _PropertyConfig(_Config):
    property: str = Field(min_length=1, max_length=240)
    source: str | None = Field(default=None, min_length=1, max_length=160)


class _ExpressionConfig(_Config):
    expression: str = Field(min_length=1)


class _LLMConfig(_Config):
    prompt: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=240)


class _ToolConfig(_Config):
    tool: str = Field(min_length=1, max_length=240)
    arguments: dict[str, Any] = Field(default_factory=dict)


class _EditTemplate(_Config):
    object_id: str = Field(min_length=1, max_length=240)
    field: str = Field(min_length=1, max_length=240)
    value: Any


class _ActionConfig(_Config):
    action: str = Field(min_length=1, max_length=240)
    edits: list[_EditTemplate] = Field(min_length=1, max_length=500)


class _ExecuteConfig(_Config):
    target: str = Field(min_length=1, max_length=240)
    request: dict[str, Any] = Field(default_factory=dict)


class _BranchPath(_Config):
    id: str = Field(min_length=1, max_length=160)
    label: str = Field(default="", max_length=240)
    condition: str = ""
    default: bool = False


class _BranchConfig(_Config):
    paths: list[_BranchPath] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _one_default(self) -> _BranchConfig:
        if sum(path.default for path in self.paths) > 1:
            raise ValueError("branch has multiple default paths")
        return self


class _HandoffConfig(_Config):
    decision: str = Field(min_length=1, max_length=4000)
    handoff_to: Literal["risk_agent", "draft_inbox", "webhook"]
    artifacts: list[Any] = Field(default_factory=list, max_length=100)
    open_qs: list[Any] = Field(default_factory=list, max_length=100)


_CONFIG_BY_KIND: dict[str, type[_Config]] = {
    "input": _InputConfig,
    "create_variable": _VariableConfig,
    "get_property": _PropertyConfig,
    "use_llm": _LLMConfig,
    "use_tool": _ToolConfig,
    "transform": _ExpressionConfig,
    "apply_action": _ActionConfig,
    "execute": _ExecuteConfig,
    "branch": _BranchConfig,
    "handoff": _HandoffConfig,
}


class _NodeFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.safe_message = message
        super().__init__(message)


class LogicDryRunPreflightError(ValueError):
    def __init__(self, code: str, message: str, node_id: str | None = None) -> None:
        self.code = code
        self.safe_message = message
        self.node_id = node_id
        super().__init__(message)


class LogicDryRunExecutor:
    def __init__(
        self,
        registry: RuntimeAdapterRegistry | None = None,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.registry = registry or RuntimeAdapterRegistry()
        self._monotonic = monotonic
        self._now = now or (lambda: datetime.now(UTC))

    def execute(
        self,
        graph: LogicGraphSnapshot,
        inputs: dict[str, Any],
        *,
        run_id: str | None = None,
        started_at: datetime | None = None,
    ) -> LogicDryRun:
        self.preflight(graph)
        started_at = started_at or self._now()
        run_started = self._monotonic()
        node_by_id = {node.id: node for node in graph.nodes}
        node_order = {node.id: index for index, node in enumerate(graph.nodes)}
        incoming = {node.id: [] for node in graph.nodes}
        outgoing = {node.id: [] for node in graph.nodes}
        for edge in graph.edges:
            incoming[edge.target_node_id].append(edge)
            outgoing[edge.source_node_id].append(edge)
        for edges in outgoing.values():
            edges.sort(key=lambda edge: (edge.order, edge.id))
        topo = self._topological_order(graph, node_order, incoming, outgoing)
        entry_ids = set(graph.entry_node_ids)
        active_edges: set[str] = set()
        results: dict[str, LogicNodeResult] = {}
        outputs: dict[str, Any] = {}
        variables: dict[str, Any] = {**inputs, "inputs": inputs}
        all_edits: list[LogicProposedEdit] = []
        run_error: LogicRunError | None = None
        usage_seen = False
        total_tokens = 0
        failed = False

        for node_id in topo:
            node = node_by_id[node_id]
            is_active = node_id in entry_ids or any(
                edge.id in active_edges for edge in incoming[node_id]
            )
            if failed:
                if node.kind == "handoff" and any(
                    results.get(edge.source_node_id) is not None
                    and results[edge.source_node_id].status in {"failed", "canceled"}
                    for edge in incoming[node_id]
                ):
                    results[node_id] = self._idle_result(
                        node.id, node.kind, "skipped", "upstream_failed"
                    )
                    continue
                reason = "fail_fast" if is_active else "not_reachable"
                status = "canceled" if is_active else "skipped"
                results[node_id] = self._idle_result(node.id, node.kind, status, reason)
                continue
            if not is_active:
                reason = "branch_not_selected" if incoming[node_id] else "not_reachable"
                results[node_id] = self._idle_result(
                    node.id, node.kind, "skipped", reason
                )
                continue
            active_parents = [
                edge.source_node_id
                for edge in incoming[node_id]
                if edge.id in active_edges
            ]
            if any(results[parent].status != "executed" for parent in active_parents):
                results[node_id] = self._idle_result(
                    node.id, node.kind, "skipped", "upstream_failed"
                )
                continue
            if self._monotonic() - run_started > MAX_TOTAL_SECONDS:
                result = self._failed_result(
                    node.id,
                    node.kind,
                    "TOTAL_TIMEOUT",
                    "dry-run total time budget exceeded",
                )
            else:
                result, output = self._execute_node(
                    node, active_parents, outputs, variables, inputs
                )
                if result.status == "executed":
                    outputs[node_id] = output
                    variables[node_id] = output
                    try:
                        validate_json_value(
                            {"variables": variables, "outputs": outputs},
                            max_bytes=MAX_TOTAL_CONTEXT_BYTES,
                        )
                    except ValueError:
                        outputs.pop(node_id, None)
                        variables.pop(node_id, None)
                        result = self._failed_result(
                            node.id,
                            node.kind,
                            "TOTAL_CONTEXT_LIMIT",
                            "dry-run total context byte limit exceeded",
                        )
            try:
                validate_json_value(
                    {
                        "node_results": [
                            item.model_dump(mode="json")
                            for item in [*results.values(), result]
                        ],
                        "proposed_edits": [
                            item.model_dump(mode="json")
                            for item in [*all_edits, *result.proposed_edits]
                        ],
                    },
                    max_bytes=MAX_TOTAL_RESULT_BYTES,
                )
            except ValueError:
                result = self._failed_result(
                    node.id,
                    node.kind,
                    "TOTAL_RESULT_LIMIT",
                    "dry-run total result byte limit exceeded",
                )
            results[node_id] = result
            all_edits.extend(result.proposed_edits)
            if result.usage is not None:
                usage_seen = True
                total_tokens += result.usage.total_tokens
            if result.status == "failed":
                failed = True
                run_error = result.error
                continue
            if node.kind == "branch":
                for edge in outgoing[node_id]:
                    if (
                        edge.branch_path == result.selected_branch_path
                        or edge.source_port == result.selected_branch_path
                    ):
                        active_edges.add(edge.id)
            else:
                active_edges.update(edge.id for edge in outgoing[node_id])

        finished_at = self._now()
        elapsed_ms = max(0, round((self._monotonic() - run_started) * 1000))
        return LogicDryRun(
            run_id=run_id or f"logic-run-{uuid.uuid4().hex}",
            graph_id=graph.id,
            status="failed" if failed else "succeeded",
            evaluated_revision=graph.revision,
            graph_hash=graph.graph_hash,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_ms=elapsed_ms,
            total_tokens=total_tokens if usage_seen else None,
            node_results=[results[node_id] for node_id in topo],
            proposed_edits=all_edits,
            error=run_error,
        )

    def execute_guarded(
        self,
        graph: LogicGraphSnapshot,
        inputs: dict[str, Any],
        *,
        run_id: str,
        started_at: datetime,
    ) -> LogicDryRun:
        """After RUNNING is durable, convert every unexpected Exception to terminal evidence."""
        guarded_started = self._monotonic()
        try:
            return self.execute(graph, inputs, run_id=run_id, started_at=started_at)
        except Exception:  # noqa: BLE001 - terminalize every unexpected runtime failure
            finished_at = self._now()
            return self.terminal_failure_evidence(
                graph,
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                elapsed_ms=max(0, round((self._monotonic() - guarded_started) * 1000)),
                code="INTERNAL_EXECUTION_ERROR",
                message="logic dry-run failed unexpectedly",
                reason="unexpected_error",
            )

    @classmethod
    def terminal_failure_evidence(
        cls,
        graph: LogicGraphSnapshot,
        *,
        run_id: str,
        started_at: datetime,
        finished_at: datetime,
        elapsed_ms: int,
        code: str,
        message: str,
        reason: str,
    ) -> LogicDryRun:
        """Build a complete deterministic terminal projection without executing nodes."""
        if not graph.nodes:
            raise LogicDryRunPreflightError(
                "LOGIC_GRAPH_EMPTY", "empty logic graph cannot produce run evidence"
            )
        node_order = {node.id: index for index, node in enumerate(graph.nodes)}
        incoming = {node.id: [] for node in graph.nodes}
        outgoing = {node.id: [] for node in graph.nodes}
        for edge in graph.edges:
            incoming[edge.target_node_id].append(edge)
            outgoing[edge.source_node_id].append(edge)
        for edges in outgoing.values():
            edges.sort(key=lambda edge: (edge.order, edge.id))
        topo = cls._topological_order(graph, node_order, incoming, outgoing)
        entry_ids = set(graph.entry_node_ids)
        failed_node_id = next(
            (node_id for node_id in topo if node_id in entry_ids), topo[0]
        )
        reachable = set(entry_ids)
        pending = list(entry_ids)
        while pending:
            source_id = pending.pop()
            for edge in outgoing.get(source_id, []):
                if edge.target_node_id not in reachable:
                    reachable.add(edge.target_node_id)
                    pending.append(edge.target_node_id)

        top_error = LogicRunError(
            code=code,
            message=message,
            node_id=failed_node_id,
            reason=reason,
        )
        node_by_id = {node.id: node for node in graph.nodes}
        node_results: list[LogicNodeResult] = []
        for node_id in topo:
            node = node_by_id[node_id]
            if node_id == failed_node_id:
                node_results.append(
                    LogicNodeResult(
                        node_id=node_id,
                        kind=node.kind,
                        status="failed",
                        started_at=started_at,
                        finished_at=finished_at,
                        elapsed_ms=elapsed_ms,
                        summary="节点执行异常终止",
                        error=top_error,
                    )
                )
            elif node_id in reachable:
                node_results.append(
                    cls._idle_result(node_id, node.kind, "canceled", "fail_fast")
                )
            else:
                node_results.append(
                    cls._idle_result(node_id, node.kind, "skipped", "not_reachable")
                )
        return LogicDryRun(
            run_id=run_id,
            graph_id=graph.id,
            status="failed",
            evaluated_revision=graph.revision,
            graph_hash=graph.graph_hash,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_ms=elapsed_ms,
            total_tokens=None,
            node_results=node_results,
            proposed_edits=[],
            error=top_error,
        )

    @staticmethod
    def _revalidate(graph: LogicGraphSnapshot) -> None:
        payload = graph.model_dump(
            mode="json",
            include={
                "name",
                "description",
                "status",
                "schema_version",
                "nodes",
                "edges",
                "entry_node_ids",
            },
        )
        if compute_logic_graph_payload_hash(payload) != graph.graph_hash:
            raise LogicGraphValidationError([])
        validation_payload = dict(payload)
        if validation_payload["status"] == "published":
            validation_payload["status"] = "draft"
        content = ValidateLogicGraphRequest.model_validate(validation_payload)
        validation = validate_logic_graph(content)
        if not validation.valid:
            raise LogicGraphValidationError(validation.issues)

    @classmethod
    def preflight(cls, graph: LogicGraphSnapshot) -> None:
        if graph.status == "archived":
            raise LogicDryRunPreflightError(
                "LOGIC_GRAPH_ARCHIVED", "archived logic graph cannot be dry-run"
            )
        if not graph.nodes:
            raise LogicDryRunPreflightError(
                "LOGIC_GRAPH_EMPTY", "empty logic graph cannot be dry-run"
            )
        cls._revalidate(graph)
        indegree = {node.id: 0 for node in graph.nodes}
        for edge in graph.edges:
            indegree[edge.target_node_id] += 1
        for entry_id in graph.entry_node_ids:
            if indegree.get(entry_id, 0) != 0:
                raise LogicDryRunPreflightError(
                    "ENTRY_NODE_HAS_INCOMING_EDGE",
                    "entry node must have zero indegree",
                    entry_id,
                )
        for node in graph.nodes:
            try:
                config = _CONFIG_BY_KIND[node.kind].model_validate(node.config)
                if node.kind == "input":
                    cls._validate_schema_shape(config.schema)
            except (ValidationError, _NodeFailure) as exc:
                raise LogicDryRunPreflightError(
                    "NODE_CONFIG_INVALID",
                    "node config does not match the canonical contract",
                    node.id,
                ) from exc

    @staticmethod
    def _topological_order(graph, node_order, incoming, outgoing) -> list[str]:
        degree = {node.id: len(incoming[node.id]) for node in graph.nodes}
        ready = sorted(
            (node.id for node in graph.nodes if degree[node.id] == 0),
            key=lambda x: (node_order[x], x),
        )
        ordered: list[str] = []
        while ready:
            node_id = ready.pop(0)
            ordered.append(node_id)
            for edge in outgoing[node_id]:
                degree[edge.target_node_id] -= 1
                if degree[edge.target_node_id] == 0:
                    ready.append(edge.target_node_id)
                    ready.sort(key=lambda x: (node_order[x], x))
        if len(ordered) != len(graph.nodes):
            raise _NodeFailure("GRAPH_CYCLE", "logic graph must be acyclic")
        return ordered

    def _execute_node(self, node, active_parents, outputs, variables, inputs):
        started_at = self._now()
        started = self._monotonic()
        usage = None
        tool_call = None
        selected = None
        edits: list[LogicProposedEdit] = []
        try:
            try:
                config = _CONFIG_BY_KIND[node.kind].model_validate(node.config)
            except ValidationError as exc:
                raise _NodeFailure(
                    "NODE_CONFIG_INVALID",
                    "node config does not match the canonical contract",
                ) from exc
            if node.kind == "input":
                self._validate_input_schema(inputs, config.schema)
                output = inputs
                summary = "输入已校验"
            elif node.kind == "create_variable":
                output = self._eval(config.expression, variables)
                variables[config.name] = output
                summary = f"变量 {config.name} 已创建"
            elif node.kind == "get_property":
                source = variables.get(config.source) if config.source else None
                if config.source and config.source not in variables:
                    raise _NodeFailure(
                        "SOURCE_NOT_FOUND", "configured property source was not found"
                    )
                if not config.source:
                    if len(active_parents) != 1:
                        raise _NodeFailure(
                            "PROPERTY_SOURCE_AMBIGUOUS", "property source is not unique"
                        )
                    source = outputs.get(active_parents[0])
                if not isinstance(source, dict) or config.property not in source:
                    raise _NodeFailure(
                        "PROPERTY_NOT_FOUND", "configured property was not found"
                    )
                output = source[config.property]
                summary = f"属性 {config.property} 已读取"
            elif node.kind == "transform":
                output = self._eval(config.expression, variables)
                summary = "表达式转换完成"
            elif node.kind == "branch":
                selected = self._select_branch(config, variables)
                output = {"selected_path": selected}
                summary = f"分支已选择 {selected}"
            elif node.kind == "handoff":
                if config.handoff_to not in HANDOFF_ALLOWLIST:
                    raise _NodeFailure(
                        "HANDOFF_TARGET_DENIED", "handoff target is not approved"
                    )
                output = {
                    "decision": config.decision,
                    "handoff_to": config.handoff_to,
                    "context_summary": f"{len(active_parents)} upstream result(s) ready",
                    "submitted": False,
                }
                summary = "移交意图已生成，未提交"
            elif node.kind == "apply_action":
                edits = [
                    LogicProposedEdit(
                        action=config.action,
                        object_id=e.object_id,
                        field=e.field,
                        value=sanitize_runtime_value(e.value)[0],
                        source_node_id=node.id,
                    )
                    for e in config.edits
                ]
                output = {
                    "action": config.action,
                    "edit_count": len(edits),
                    "applied": False,
                }
                summary = f"已生成 {len(edits)} 条变更提议，未写入"
            elif node.kind == "execute":
                adapter, adapter_result = self.registry.preview_execute(
                    config.target, config.request, timeout_seconds=MAX_NODE_SECONDS
                )
                preview, _ = sanitize_runtime_value(adapter_result.preview)
                output = {
                    "target": config.target,
                    "request": "[OMITTED]",
                    "preview": preview,
                    "adapter": adapter,
                    "executed": False,
                }
                summary = "沙箱目标预览已生成，未执行"
            elif node.kind == "use_llm":
                adapter, adapter_result = self.registry.invoke_llm(
                    config.model,
                    self._render(config.prompt, variables),
                    timeout_seconds=MAX_NODE_SECONDS,
                )
                usage = adapter_result.usage
                encoded = adapter_result.output.encode("utf-8")
                output = {
                    "model": config.model,
                    "adapter": adapter,
                    "response_summary": "LLM response omitted from dry-run history",
                    "response_length": len(adapter_result.output),
                    "response_hash": hashlib.sha256(encoded).hexdigest(),
                }
                summary = "LLM dry-run adapter 调用完成"
            elif node.kind == "use_tool":
                registration, adapter_result = self.registry.invoke_tool(
                    config.tool, config.arguments, timeout_seconds=MAX_NODE_SECONDS
                )
                output, _ = sanitize_runtime_value(adapter_result.output)
                tool_call = LogicToolCall(
                    tool=config.tool,
                    adapter=registration.adapter_name,
                    read_only=True,
                    dry_run_safe=True,
                )
                summary = "只读 dry-run 工具调用完成"
            else:  # pragma: no cover - graph model already restricts kinds
                raise _NodeFailure("UNKNOWN_NODE_KIND", "unknown logic node kind")
            safe_output, truncated = sanitize_runtime_value(output)
            validate_json_value(safe_output)
            if self._monotonic() - started > MAX_NODE_SECONDS:
                raise _NodeFailure("NODE_TIMEOUT", "node time budget exceeded")
            finished_at = self._now()
            return LogicNodeResult(
                node_id=node.id,
                kind=node.kind,
                status="executed",
                started_at=started_at,
                finished_at=finished_at,
                elapsed_ms=max(0, round((self._monotonic() - started) * 1000)),
                summary=summary,
                output=safe_output,
                usage=usage,
                tool_call=tool_call,
                selected_branch_path=selected,
                proposed_edits=edits,
                truncated=truncated,
            ), output
        except (LogicAdapterError, _NodeFailure) as exc:
            code = exc.code
            message = exc.safe_message
        except FunctionError:
            code, message = (
                "EXPRESSION_FAILED",
                "canonical expression evaluation failed",
            )
        except (ValueError, TypeError):
            code, message = (
                "NODE_OUTPUT_INVALID",
                "node produced an invalid or oversized result",
            )
        finished_at = self._now()
        error = LogicRunError(code=code, message=message, node_id=node.id)
        return LogicNodeResult(
            node_id=node.id,
            kind=node.kind,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            elapsed_ms=max(0, round((self._monotonic() - started) * 1000)),
            summary="节点执行失败",
            error=error,
        ), None

    @staticmethod
    def _eval(expression: str, variables: dict[str, Any]) -> Any:
        value = evaluate(parse(expression), variables)
        validate_json_value(value)
        return value

    @staticmethod
    def _select_branch(config: _BranchConfig, variables: dict[str, Any]) -> str:
        default_id = None
        for path in config.paths:
            if path.default:
                default_id = path.id
                continue
            if not path.condition or path.condition == "default":
                raise _NodeFailure(
                    "BRANCH_CONDITION_INVALID",
                    "non-default branch path requires a condition",
                )
            if bool(LogicDryRunExecutor._eval(path.condition, variables)):
                return path.id
        if default_id is None:
            raise _NodeFailure(
                "BRANCH_NO_MATCH", "branch has no matching or default path"
            )
        return default_id

    @staticmethod
    def _validate_input_schema(inputs: dict[str, Any], schema: dict[str, Any]) -> None:
        if not schema:
            return
        LogicDryRunExecutor._validate_schema_shape(schema)
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        for key in required:
            if key not in inputs:
                raise _NodeFailure("INPUT_SCHEMA_MISMATCH", "required input is missing")
        types = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
            "null": type(None),
        }
        for key, rule in properties.items():
            if key not in inputs or "type" not in rule:
                continue
            expected = types[rule["type"]]
            if not isinstance(inputs[key], expected) or (
                rule["type"] in {"number", "integer"} and isinstance(inputs[key], bool)
            ):
                raise _NodeFailure(
                    "INPUT_SCHEMA_MISMATCH", "input type does not match schema"
                )

    @staticmethod
    def _validate_schema_shape(schema: dict[str, Any]) -> None:
        if not schema:
            return
        if schema.get("type", "object") != "object":
            raise _NodeFailure(
                "INPUT_SCHEMA_INVALID", "input schema must describe an object"
            )
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if not isinstance(required, list) or not isinstance(properties, dict):
            raise _NodeFailure("INPUT_SCHEMA_INVALID", "input schema is invalid")
        for key in required:
            if not isinstance(key, str):
                raise _NodeFailure(
                    "INPUT_SCHEMA_INVALID", "required input names must be strings"
                )
        supported = {
            "string",
            "number",
            "integer",
            "boolean",
            "object",
            "array",
            "null",
        }
        for key, rule in properties.items():
            if not isinstance(key, str) or not isinstance(rule, dict):
                raise _NodeFailure(
                    "INPUT_SCHEMA_INVALID", "input property schema is invalid"
                )
            if "type" in rule and rule["type"] not in supported:
                raise _NodeFailure(
                    "INPUT_SCHEMA_INVALID", "unsupported input schema type"
                )

    @staticmethod
    def _render(template: str, variables: dict[str, Any]) -> str:
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace("{{" + key + "}}", str(value))
        return rendered

    @staticmethod
    def _idle_result(
        node_id: str, kind: str, status: str, reason: str
    ) -> LogicNodeResult:
        return LogicNodeResult(
            node_id=node_id,
            kind=kind,
            status=status,
            summary="节点未执行",
            error=LogicRunError(
                code=status.upper(),
                message="node was not executed",
                node_id=node_id,
                reason=reason,
            ),
        )

    @staticmethod
    def _failed_result(
        node_id: str, kind: str, code: str, message: str
    ) -> LogicNodeResult:
        return LogicNodeResult(
            node_id=node_id,
            kind=kind,
            status="failed",
            summary="节点执行失败",
            error=LogicRunError(code=code, message=message, node_id=node_id),
        )
