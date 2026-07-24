"""W2-#7 · AIP/LLM 节点。

7 种 AIP 模板（generate/explain/name/assistant/extract/sentiment/summarize）+
逐行 LLM 节点执行器。Pipeline 通过 kind="llm" 节点接入。

LLM 调用经 chat_fn 注入（默认 llm_gateway.chat），不写死模型。

详见 docs/palantier/20_tech/220tech_w2-b-aip-functions.md §2.1。
"""
from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, Field


AipTemplateKind = Literal[
    "generate",
    "explain",
    "name",
    "assistant",
    "extract",
    "sentiment",
    "summarize",
]


class AipTemplate(BaseModel):
    kind: AipTemplateKind
    name: str
    description: str
    default_prompt: str
    output_hint: str = "answer"


class AipError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_DEFAULT_TEMPLATES: list[AipTemplate] = [
    AipTemplate(
        kind="generate",
        name="生成",
        description="根据输入生成自由文本内容",
        default_prompt="请基于以下内容生成一段文字：\n{{input}}",
    ),
    AipTemplate(
        kind="explain",
        name="解释",
        description="用通俗语言解释输入内容",
        default_prompt="请用通俗语言解释以下内容：\n{{input}}",
    ),
    AipTemplate(
        kind="name",
        name="命名",
        description="为输入内容生成简洁名称",
        default_prompt="请为以下内容生成一个简洁的名称（不超过 20 字）：\n{{input}}",
        output_hint="name",
    ),
    AipTemplate(
        kind="assistant",
        name="助手",
        description="作为助手回答关于输入的问题",
        default_prompt="你是智能助手。针对以下内容回答问题：\n{{input}}",
    ),
    AipTemplate(
        kind="extract",
        name="抽取",
        description="从输入中抽取结构化信息（JSON）",
        default_prompt="从以下内容中抽取关键信息，输出 JSON：\n{{input}}",
        output_hint="extracted",
    ),
    AipTemplate(
        kind="sentiment",
        name="情感分析",
        description="判断输入的情感倾向（正向/负向/中性）",
        default_prompt="判断以下内容的情感倾向（正向/负向/中性），仅输出一个词：\n{{input}}",
        output_hint="sentiment",
    ),
    AipTemplate(
        kind="summarize",
        name="摘要",
        description="生成输入内容的简短摘要",
        default_prompt="请用一句话总结以下内容：\n{{input}}",
        output_hint="summary",
    ),
]

AIP_TEMPLATE_REGISTRY: dict[str, AipTemplate] = {t.kind: t for t in _DEFAULT_TEMPLATES}


ChatFn = Callable[..., dict[str, Any]]


def _render(template: str, variables: dict[str, Any]) -> str:
    result = template
    for key, val in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(val))
    return result


def render_template(
    kind: AipTemplateKind, row: dict[str, Any], user_prompt: str | None = None
) -> str:
    template = AIP_TEMPLATE_REGISTRY.get(kind)
    if template is None:
        raise AipError("UNKNOWN_TEMPLATE", f"未知 AIP 模板 {kind!r}，可用：{list(AIP_TEMPLATE_REGISTRY.keys())}")
    prompt_text = user_prompt if user_prompt else template.default_prompt
    input_value = row.get("input", "") or _row_to_text(row)
    return _render(prompt_text, {**row, "input": input_value})


def _row_to_text(row: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v}" for k, v in row.items() if not k.startswith("_"))


def execute_llm_node(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    chat_fn: ChatFn | None = None,
) -> list[dict[str, Any]]:
    """逐行渲染模板→调用 chat→把答案写入 output_column。

    config 字段：
      - template: AipTemplateKind（必填）
      - prompt: 自定义 prompt（可选，覆盖模板默认）
      - input_column: 取该列作为 {{input}}（可选，默认取整行）
      - output_column: 写入该列（默认 "llm_output"）
      - model: 模型名（可选，经 gateway 路由）
    """
    if chat_fn is None:
        from .llm_gateway import chat as _default_chat
        chat_fn = _default_chat

    template_kind = config.get("template")
    if not template_kind:
        raise AipError("MISSING_TEMPLATE", "llm 节点缺少 template 配置")
    if template_kind not in AIP_TEMPLATE_REGISTRY:
        raise AipError("UNKNOWN_TEMPLATE", f"未知模板 {template_kind!r}")

    user_prompt = config.get("prompt")
    input_column = config.get("input_column")
    output_column = config.get("output_column", "llm_output")
    model = config.get("model", "")

    result_rows: list[dict[str, Any]] = []
    for row in rows:
        scoped_row = dict(row)
        if input_column:
            scoped_row["input"] = row.get(input_column, "")
        rendered = render_template(template_kind, scoped_row, user_prompt)
        chat_kwargs: dict[str, Any] = {}
        if model:
            chat_kwargs["model"] = model
        try:
            resp = chat_fn(rendered, **chat_kwargs)
        except Exception as exc:
            raise AipError("LLM_CALL_FAILED", f"LLM 调用失败：{exc}") from exc
        answer = resp.get("answer", "") if isinstance(resp, dict) else str(resp)
        new_row = {**row, output_column: answer}
        result_rows.append(new_row)
    return result_rows


def list_templates() -> list[AipTemplate]:
    return [t.model_copy() for t in AIP_TEMPLATE_REGISTRY.values()]
