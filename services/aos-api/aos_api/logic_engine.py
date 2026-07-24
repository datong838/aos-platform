"""W1-2 · Logic 编排引擎。

7 种 Block + 块链顺序执行器 + 调试器（CoT/Edits）+ Edits 合并策略 + Prompt 工程。
UseLLM Block 通过 chat_fn 调用 LLM（默认 llm_gateway.chat），不写死模型。
ApplyAction Block 通过 shell_core 写回（调试模式只收集 proposed_edits）。

详见 docs/palantier/20_tech/220tech_logic-engine.md。
"""
from __future__ import annotations

import uuid
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from .function_engine import FunctionError, evaluate, parse


BlockKind = Literal[
    "input",
    "create_variable",
    "get_property",
    "use_llm",
    "use_tool",
    "transform",
    "apply_action",
    "execute",
]

MergeStrategy = Literal["last_write_wins", "field_level", "manual_review"]


class Block(BaseModel):
    id: str = Field(default_factory=lambda: "blk-" + uuid.uuid4().hex[:8])
    kind: BlockKind
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    wiki_ref: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    condition: str = ""


class LogicGraph(BaseModel):
    nodes: list[Block] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    entry: str = ""


class BlockResult(BaseModel):
    block_id: str
    output: Any = None
    cot: list[str] = Field(default_factory=list)
    proposed_edits: list[dict[str, Any]] = Field(default_factory=list)


class ExecutionContext(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    results: list[BlockResult] = Field(default_factory=list)
    cot: list[str] = Field(default_factory=list)
    proposed_edits: list[dict[str, Any]] = Field(default_factory=list)


class EditEntry(BaseModel):
    pk: str
    field: str
    value: Any
    source_block_id: str


class LogicError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class LogicEngine:
    def __init__(
        self,
        chat_fn: Callable[..., dict[str, Any]] | None = None,
        tool_registry: "Any | None" = None,
        wiki_loader: Callable[[str], str | None] | None = None,
    ) -> None:
        if chat_fn is None:
            from .llm_gateway import chat as _default_chat
            chat_fn = _default_chat
        self._chat_fn = chat_fn
        if tool_registry is None:
            from .tool_registry import get_registry as _get_registry
            tool_registry = _get_registry()
        self._tool_registry = tool_registry
        self._wiki_loader = wiki_loader or _default_wiki_loader

    def run(
        self,
        blocks: list[Block],
        inputs: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> ExecutionContext:
        ctx = ExecutionContext(variables=dict(inputs or {}))
        for block in blocks:
            self._inject_wiki(block, ctx)
            result = self._exec_block(block, ctx, debug)
            ctx.results.append(result)
            ctx.cot.extend(result.cot)
            ctx.proposed_edits.extend(result.proposed_edits)
        return ctx

    def run_graph(
        self,
        graph: LogicGraph,
        inputs: dict[str, Any] | None = None,
        debug: bool = False,
        max_steps: int = 256,
    ) -> ExecutionContext:
        ctx = ExecutionContext(variables=dict(inputs or {}))
        node_map = {n.id: n for n in graph.nodes}
        edges_from: dict[str, list[GraphEdge]] = {}
        for e in graph.edges:
            edges_from.setdefault(e.source, []).append(e)
        current = graph.entry
        steps = 0
        while current and steps < max_steps:
            steps += 1
            block = node_map.get(current)
            if block is None:
                break
            self._inject_wiki(block, ctx)
            result = self._exec_block(block, ctx, debug)
            ctx.results.append(result)
            ctx.cot.extend(result.cot)
            ctx.proposed_edits.extend(result.proposed_edits)
            out_edges = edges_from.get(current, [])
            nxt = None
            default_nxt = None
            for e in out_edges:
                if not e.condition:
                    default_nxt = e.target
                    continue
                try:
                    if evaluate(parse(e.condition), ctx.variables):
                        nxt = e.target
                        break
                except Exception:
                    continue
            if nxt is None:
                nxt = default_nxt
            current = nxt
        return ctx

    def _inject_wiki(self, block: Block, ctx: ExecutionContext) -> None:
        if not block.wiki_ref:
            return
        try:
            doc = self._wiki_loader(block.wiki_ref)
        except Exception:
            doc = None
        if doc:
            ctx.variables[f"_wiki_{block.id}"] = doc

    def _exec_block(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        handler = {
            "input": self._blk_input,
            "create_variable": self._blk_create_variable,
            "get_property": self._blk_get_property,
            "use_llm": self._blk_use_llm,
            "use_tool": self._blk_use_tool,
            "transform": self._blk_transform,
            "apply_action": self._blk_apply_action,
            "execute": self._blk_execute,
        }.get(block.kind)
        if handler is None:
            raise LogicError("UNKNOWN_BLOCK", f"未知的 Block 类型：{block.kind}")
        return handler(block, ctx, debug)

    def _blk_input(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        ctx.variables.update(block.config)
        return BlockResult(block_id=block.id, output=block.config)

    def _blk_create_variable(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        var_name = block.config.get("name") or block.name
        expr = block.config.get("expr", "")
        if not var_name:
            raise LogicError("MISSING_NAME", "create_variable 缺少 name")
        try:
            value = evaluate(parse(expr), ctx.variables) if expr else None
        except FunctionError as exc:
            raise LogicError("EXPR_ERROR", f"表达式错误：{exc.message}") from exc
        ctx.variables[var_name] = value
        return BlockResult(block_id=block.id, output={var_name: value})

    def _blk_get_property(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        source = block.config.get("source", "")
        prop = block.config.get("property", "")
        var_name = block.config.get("as") or f"{source}_{prop}"
        obj = ctx.variables.get(source)
        if obj is None:
            raise LogicError("SOURCE_NOT_FOUND", f"源变量 {source} 不存在")
        if isinstance(obj, dict):
            value = obj.get(prop)
        else:
            value = getattr(obj, prop, None)
        ctx.variables[var_name] = value
        return BlockResult(block_id=block.id, output={var_name: value})

    def _blk_use_llm(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        prompt_template = block.config.get("prompt", "")
        system_prompt = block.config.get("system_prompt", "")
        model = block.config.get("model", "")
        few_shot = block.config.get("few_shot", [])
        tools = block.config.get("tools", [])

        rendered = _render_prompt(prompt_template, ctx.variables)
        parts: list[str] = []
        for shot in few_shot:
            parts.append(_render_prompt(str(shot), ctx.variables))
        parts.append(rendered)
        full_prompt = "\n---\n".join(parts) if parts else rendered

        cot_entry = f"[UseLLM] model={model or 'default'} prompt={full_prompt[:120]}"
        chat_kwargs: dict[str, Any] = {}
        if model:
            chat_kwargs["model"] = model
        if tools:
            chat_kwargs["with_tools"] = True
            chat_kwargs["tools"] = tools

        try:
            resp = self._chat_fn(full_prompt, **chat_kwargs)
        except Exception as exc:
            raise LogicError("LLM_CALL_FAILED", f"LLM 调用失败：{exc}") from exc

        answer = resp.get("answer", "") if isinstance(resp, dict) else str(resp)
        var_name = block.config.get("output_var") or f"llm_{block.id}"
        ctx.variables[var_name] = answer
        return BlockResult(
            block_id=block.id,
            output=answer,
            cot=[cot_entry, f"[UseLLM] answer={answer[:120]}"],
        )

    def _blk_use_tool(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        tool_ref = block.config.get("tool_id") or block.config.get("tool_ref") or ""
        args = block.config.get("args", {})
        if isinstance(args, dict):
            rendered_args = {
                k: (_render_prompt(str(v), ctx.variables) if isinstance(v, str) and "{{" in v else v)
                for k, v in args.items()
            }
        else:
            rendered_args = args
        if not tool_ref:
            raise LogicError("MISSING_TOOL", "use_tool 缺少 tool_id")
        from .tool_registry import ToolError
        try:
            result = self._tool_registry.invoke(tool_ref, rendered_args)
        except ToolError as exc:
            raise LogicError(exc.code, exc.message) from exc
        var_name = block.config.get("output_var") or f"tool_{block.id}"
        ctx.variables[var_name] = result
        return BlockResult(
            block_id=block.id,
            output=result,
            cot=[f"[UseTool] tool={tool_ref} args={rendered_args} → {str(result)[:120]}"],
        )

    def _blk_transform(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        expr = block.config.get("expr", "")
        var_name = block.config.get("output_var") or f"transform_{block.id}"
        try:
            value = evaluate(parse(expr), ctx.variables)
        except FunctionError as exc:
            raise LogicError("EXPR_ERROR", f"Transform 表达式错误：{exc.message}") from exc
        ctx.variables[var_name] = value
        return BlockResult(block_id=block.id, output=value)

    def _blk_apply_action(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        action_ref = block.config.get("action_ref", "")
        edits_config = block.config.get("edits", [])
        edits: list[EditEntry] = []
        for e in edits_config:
            field_val = e.get("value")
            if isinstance(field_val, str) and "{{" in field_val:
                field_val = _render_prompt(field_val, ctx.variables)
            edits.append(EditEntry(
                pk=str(e.get("pk", "")),
                field=e.get("field", ""),
                value=field_val,
                source_block_id=block.id,
            ))
        proposed = [e.model_dump() for e in edits]
        if debug:
            return BlockResult(
                block_id=block.id,
                output={"edits": proposed, "applied": False},
                proposed_edits=proposed,
                cot=[f"[ApplyAction] debug 模式：收集 {len(edits)} 条 proposed_edits（不落库）"],
            )
        merged = merge_edits(edits, "last_write_wins")
        return BlockResult(
            block_id=block.id,
            output={"edits": [e.model_dump() for e in merged], "applied": True, "action_ref": action_ref},
            cot=[f"[ApplyAction] 写回 {len(merged)} 条 edits 到 action={action_ref}"],
        )

    def _blk_execute(
        self, block: Block, ctx: ExecutionContext, debug: bool
    ) -> BlockResult:
        query = block.config.get("query", "")
        var_name = block.config.get("output_var") or f"exec_{block.id}"
        rendered = _render_prompt(query, ctx.variables)
        ctx.variables[var_name] = {"query": rendered, "results": []}
        return BlockResult(
            block_id=block.id,
            output=ctx.variables[var_name],
            cot=[f"[Execute] query={rendered[:120]}"],
        )


def _default_wiki_loader(wiki_ref: str) -> str | None:
    """从 KV store 读取 wiki 文档摘要；不存在/异常返回 None（不中断执行）。"""
    try:
        from .aip_kv_store import kv_get

        doc = kv_get(f"wiki:{wiki_ref}")
        if isinstance(doc, dict):
            return str(doc.get("summary") or doc.get("text") or "")
        if isinstance(doc, str):
            return doc
        return None
    except Exception:
        return None


def _render_prompt(template: str, variables: dict[str, Any]) -> str:
    result = template
    for key, val in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(val))
    return result


def merge_edits(
    edits: list[EditEntry], strategy: MergeStrategy
) -> list[EditEntry]:
    if not edits:
        return []
    if strategy == "last_write_wins":
        seen: dict[str, EditEntry] = {}
        for e in edits:
            seen[f"{e.pk}::{e.field}"] = e
        return list(seen.values())
    if strategy == "field_level":
        grouped: dict[str, dict[str, EditEntry]] = {}
        for e in edits:
            grouped.setdefault(e.pk, {})[e.field] = e
        result: list[EditEntry] = []
        for _pk, fields in grouped.items():
            result.extend(fields.values())
        return result
    return list(edits)


BLOCK_CATALOG: list[dict[str, Any]] = [
    {"kind": "input", "name": "Input", "description": "接收入参"},
    {"kind": "create_variable", "name": "Create Variable", "description": "创建变量（表达式）"},
    {"kind": "get_property", "name": "Get Property", "description": "获取对象属性"},
    {"kind": "use_llm", "name": "Use LLM", "description": "调用 LLM（提示+工具+变量注入）"},
    {"kind": "use_tool", "name": "Use Tool", "description": "调用已注册工具（Capability 深度集成）"},
    {"kind": "transform", "name": "Transform", "description": "调用 Function 引擎变换"},
    {"kind": "apply_action", "name": "Apply Action", "description": "调用 Action 写回 Ontology"},
    {"kind": "execute", "name": "Execute", "description": "执行子流程/语义搜索"},
]


_engine = LogicEngine()


def get_engine() -> LogicEngine:
    return _engine
