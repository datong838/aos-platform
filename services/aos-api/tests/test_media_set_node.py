"""W2-#2 · 媒体集→表格行节点测试。"""
from __future__ import annotations

import pytest

from aos_api.media_reference import MediaReferenceStore
from aos_api.media_set import MediaSetStore
from aos_api.pipeline_builder import (
    Pipeline,
    PipelineEditor,
    PipelineEditorError,
    PipelineNode,
)


@pytest.fixture
def setup_media(monkeypatch):
    ref_store = MediaReferenceStore()
    r1 = ref_store.register(kind="image", storage="local", bucket="t", path="a.png", size_bytes=100)
    r2 = ref_store.register(kind="image", storage="local", bucket="t", path="b.png", size_bytes=200)
    import aos_api.media_set as ms_mod
    monkeypatch.setattr(ms_mod, "get_media_store", lambda: ref_store)
    ms_store = ms_mod.get_store()
    ms_store._sets.clear()
    ms = ms_store.create("imgs", "image")
    ms_store.add_media(ms.id, r1.id)
    ms_store.add_media(ms.id, r2.id)
    yield ms_store, ms.id
    ms_store._sets.clear()


def test_media_set_node_kind_accepted():
    node = PipelineNode(id="ms1", kind="media_set", media_set_id="ms-123")
    assert node.kind == "media_set"
    assert node.media_set_id == "ms-123"


def test_media_set_node_validate_missing_id():
    pipeline = Pipeline(id="p1", name="t", nodes=[PipelineNode(id="n1", kind="media_set")])
    editor = PipelineEditor(pipeline)
    errors = editor.validate()
    assert any("MEDIA_SET_NO_ID" in e for e in errors)


def test_media_set_node_validate_with_id():
    pipeline = Pipeline(id="p1", name="t", nodes=[PipelineNode(id="n1", kind="media_set", media_set_id="ms-1")])
    editor = PipelineEditor(pipeline)
    errors = editor.validate()
    assert not any("MEDIA_SET_NO_ID" in e for e in errors)


def test_media_set_node_preview_loads_rows(setup_media):
    ms_store, ms_id = setup_media
    pipeline = Pipeline(
        id="p2", name="ms-pipe",
        nodes=[PipelineNode(id="ms-src", kind="media_set", media_set_id=ms_id)],
        edges=[],
    )
    editor = PipelineEditor(pipeline)
    outputs = editor.preview({})
    assert len(outputs["ms-src"]) == 2
    assert "media_ref_id" in outputs["ms-src"][0]


def test_media_set_to_transform_chain(setup_media):
    ms_store, ms_id = setup_media
    pipeline = Pipeline(
        id="p3", name="chain",
        nodes=[
            PipelineNode(id="ms", kind="media_set", media_set_id=ms_id),
            PipelineNode(id="filter", kind="transform", op="filter", config={"expression": "size_bytes > 150"}),
        ],
        edges=[{"src": "ms", "dst": "filter"}],
    )
    editor = PipelineEditor(pipeline)
    outputs = editor.preview({})
    assert len(outputs["filter"]) == 1
    assert outputs["filter"][0]["size_bytes"] == 200


def test_media_set_node_field_persists():
    node = PipelineNode(id="n", kind="media_set", media_set_id="abc", label="图片源")
    data = node.model_dump()
    assert data["media_set_id"] == "abc"
    assert data["kind"] == "media_set"


def test_apply_node_op_ignores_media_set_directly():
    editor = PipelineEditor(Pipeline(id="p", name="t"))
    result = editor._apply_node_op(PipelineNode(id="n", kind="transform", op="filter"), [{"x": 1}])
    assert result == [{"x": 1}]


def test_pipeline_with_all_four_kinds_validates(setup_media):
    ms_store, ms_id = setup_media
    pipeline = Pipeline(
        id="p4", name="all-kinds",
        nodes=[
            PipelineNode(id="ds", kind="dataset", label="d"),
            PipelineNode(id="ms", kind="media_set", media_set_id=ms_id),
            PipelineNode(id="tf", kind="transform", op="union", config={"other": []}),
            PipelineNode(id="llm", kind="llm", config={"template": "generate"}),
        ],
        edges=[{"src": "ds", "dst": "tf"}],
    )
    editor = PipelineEditor(pipeline)
    errors = editor.validate()
    assert not any("MEDIA_SET" in e or "DATASET" in e or "LLM" in e for e in errors)
