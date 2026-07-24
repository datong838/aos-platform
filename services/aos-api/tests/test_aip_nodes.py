"""W2-#7 · AIP/LLM 节点测试。"""
from __future__ import annotations

import pytest

from aos_api.aip_nodes import (
    AIP_TEMPLATE_REGISTRY,
    AipError,
    execute_llm_node,
    list_templates,
    render_template,
)
from aos_api.pipeline_builder import (
    Pipeline,
    PipelineEditor,
    PipelineEditorError,
    PipelineNode,
)


def _mock_chat_factory(answer: str = "MOCK-ANSWER"):
    def chat(query, **kwargs):
        return {"answer": f"{answer}::{query[:30]}"}
    return chat


# ---------- 模板测试 ----------


def test_seven_templates_registered():
    templates = list_templates()
    kinds = {t.kind for t in templates}
    expected = {"generate", "explain", "name", "assistant", "extract", "sentiment", "summarize"}
    assert kinds == expected


def test_render_template_substitutes_input():
    rendered = render_template("summarize", {"input": "一段文本"})
    assert "一段文本" in rendered


def test_render_template_with_row_fields():
    rendered = render_template("name", {"title": "产品A", "desc": "描述"})
    # {{input}} 应被填充为整行文本（包含 title）
    assert "title=产品A" in rendered


def test_render_custom_user_prompt():
    rendered = render_template("generate", {"input": "X"}, user_prompt="自定义：{{input}}")
    assert rendered == "自定义：X"


def test_render_unknown_template_raises():
    with pytest.raises(AipError) as exc:
        render_template("bogus", {"input": ""})
    assert exc.value.code == "UNKNOWN_TEMPLATE"


# ---------- LLM 节点执行测试 ----------


def test_execute_llm_node_writes_output_column():
    rows = [{"id": 1, "text": "hello"}, {"id": 2, "text": "world"}]
    result = execute_llm_node(
        rows,
        {"template": "summarize", "input_column": "text", "output_column": "summary"},
        chat_fn=_mock_chat_factory("SUM"),
    )
    assert all("summary" in r for r in result)
    assert result[0]["summary"].startswith("SUM::")


def test_execute_llm_node_default_output_column():
    result = execute_llm_node(
        [{"x": 1}],
        {"template": "explain"},
        chat_fn=_mock_chat_factory(),
    )
    assert "llm_output" in result[0]


def test_execute_llm_node_missing_template_raises():
    with pytest.raises(AipError) as exc:
        execute_llm_node([{"x": 1}], {"template": ""}, chat_fn=_mock_chat_factory())
    assert exc.value.code == "MISSING_TEMPLATE"


def test_execute_llm_node_unknown_template_raises():
    with pytest.raises(AipError) as exc:
        execute_llm_node([{"x": 1}], {"template": "nope"}, chat_fn=_mock_chat_factory())
    assert exc.value.code == "UNKNOWN_TEMPLATE"


def test_execute_llm_node_chat_failure_wrapped():
    def bad_chat(query, **kwargs):
        raise RuntimeError("network down")

    with pytest.raises(AipError) as exc:
        execute_llm_node([{"x": 1}], {"template": "generate"}, chat_fn=bad_chat)
    assert exc.value.code == "LLM_CALL_FAILED"


def test_execute_llm_node_empty_rows():
    result = execute_llm_node([], {"template": "generate"}, chat_fn=_mock_chat_factory())
    assert result == []


# ---------- Pipeline 集成测试 ----------


def test_pipeline_llm_node_validate_requires_template():
    pipeline = Pipeline(id="p1", name="t", nodes=[PipelineNode(id="n1", kind="llm", config={})])
    editor = PipelineEditor(pipeline)
    errors = editor.validate()
    assert any("LLM_NO_TEMPLATE" in e for e in errors)


def test_pipeline_llm_node_preview_executes(monkeypatch):
    monkeypatch.setattr(
        "aos_api.aip_nodes.execute_llm_node",
        lambda rows, config, chat_fn=None: [{**r, "llm_output": "OK"} for r in rows],
    )
    pipeline = Pipeline(
        id="p2",
        name="llm-pipe",
        nodes=[
            PipelineNode(id="src", kind="dataset", label="ds"),
            PipelineNode(id="llm1", kind="llm", config={"template": "summarize"}),
        ],
        edges=[{"src": "src", "dst": "llm1"}],
    )
    editor = PipelineEditor(pipeline)
    outputs = editor.preview({"src": [{"a": 1}]})
    assert outputs["llm1"] == [{"a": 1, "llm_output": "OK"}]
