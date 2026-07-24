"""W2-#22 · Web IDE 测试。"""
from __future__ import annotations

import pytest

from aos_api.web_ide import IdeError, WebIdeEngine


@pytest.fixture
def engine() -> WebIdeEngine:
    return WebIdeEngine()


# ---------- 会话管理 ----------


def test_create_session_has_default_file(engine: WebIdeEngine):
    session = engine.create_session("test")
    assert "main.py" in session.files
    assert session.open_file == "main.py"
    assert "def transform" in session.files["main.py"].content


def test_get_session(engine: WebIdeEngine):
    session = engine.create_session()
    assert engine.get_session(session.id).id == session.id


def test_get_unknown_session_raises(engine: WebIdeEngine):
    with pytest.raises(IdeError) as exc:
        engine.get_session("ghost")
    assert exc.value.code == "SESSION_NOT_FOUND"


def test_delete_session(engine: WebIdeEngine):
    session = engine.create_session()
    assert engine.delete_session(session.id) is True
    assert engine.delete_session(session.id) is False


def test_list_sessions(engine: WebIdeEngine):
    engine.create_session("a")
    engine.create_session("b")
    assert len(engine.list_sessions()) >= 2


# ---------- 文件操作 ----------


def test_create_and_write_file(engine: WebIdeEngine):
    session = engine.create_session()
    f = engine.create_file(session.id, "util.py", "def helper():\n    return 42\n")
    assert f.path == "util.py"
    assert "helper" in f.content


def test_create_duplicate_file_raises(engine: WebIdeEngine):
    session = engine.create_session()
    engine.create_file(session.id, "a.py")
    with pytest.raises(IdeError) as exc:
        engine.create_file(session.id, "a.py")
    assert exc.value.code == "FILE_EXISTS"


def test_delete_file(engine: WebIdeEngine):
    session = engine.create_session()
    engine.create_file(session.id, "temp.py", "x = 1")
    assert engine.delete_file(session.id, "temp.py") is True
    assert engine.delete_file(session.id, "temp.py") is False


def test_open_file(engine: WebIdeEngine):
    session = engine.create_session()
    engine.create_file(session.id, "other.py", "print('hi')")
    f = engine.open_file(session.id, "other.py")
    assert engine.get_session(session.id).open_file == "other.py"


def test_open_unknown_file_raises(engine: WebIdeEngine):
    session = engine.create_session()
    with pytest.raises(IdeError) as exc:
        engine.open_file(session.id, "ghost.py")
    assert exc.value.code == "FILE_NOT_FOUND"


# ---------- 诊断 ----------


def test_diagnostics_clean_code(engine: WebIdeEngine):
    session = engine.create_session()
    diags = engine.diagnostics(session.id)
    assert diags == []


def test_diagnostics_detects_blocked_import(engine: WebIdeEngine):
    session = engine.create_session()
    engine.write_file(session.id, "main.py", "import os\ndef transform(rows):\n    return rows\n")
    diags = engine.diagnostics(session.id)
    assert len(diags) >= 1
    assert all(d.severity == "error" for d in diags)


def test_diagnostics_detects_missing_transform(engine: WebIdeEngine):
    session = engine.create_session()
    engine.write_file(session.id, "main.py", "x = 1\n")
    diags = engine.diagnostics(session.id)
    assert any("transform" in d.message for d in diags)


# ---------- 补全 ----------


def test_completions_empty_prefix_returns_keywords(engine: WebIdeEngine):
    session = engine.create_session()
    comps = engine.completions(session.id, "")
    labels = {c.label for c in comps}
    assert "len" in labels
    assert "def transform" in labels


def test_completions_with_prefix_filters(engine: WebIdeEngine):
    session = engine.create_session()
    comps = engine.completions(session.id, "de")
    labels = {c.label for c in comps}
    assert any("def" in l.lower() or "def transform" in l for l in labels)


def test_completions_include_ast_functions(engine: WebIdeEngine):
    session = engine.create_session()
    engine.write_file(session.id, "main.py", "def my_func(x):\n    return x\ndef transform(rows):\n    return rows\n")
    comps = engine.completions(session.id, "my")
    labels = {c.label for c in comps}
    assert "my_func" in labels


# ---------- 符号 ----------


def test_symbols_extract_functions(engine: WebIdeEngine):
    session = engine.create_session()
    engine.write_file(session.id, "main.py", "def foo():\n    pass\ndef transform(rows):\n    return rows\n")
    symbols = engine.symbols(session.id)
    names = {s.name for s in symbols}
    assert "foo" in names
    assert "transform" in names


def test_hover_returns_function_signature(engine: WebIdeEngine):
    session = engine.create_session()
    engine.write_file(session.id, "main.py", "def add(a, b):\n    '''求和'''\n    return a + b\ndef transform(rows):\n    return rows\n")
    hover = engine.hover(session.id, line=1)
    assert "add" in hover.signature
    assert "求和" in hover.docstring
