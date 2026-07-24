"""W2-#25 · 多语言 Transform 测试。"""
from __future__ import annotations

import pytest

from aos_api.multi_language_transform import (
    MultiLanguageError,
    MultiLanguageTransform,
    list_supported_languages,
)


@pytest.fixture
def engine() -> MultiLanguageTransform:
    return MultiLanguageTransform()


def test_supported_languages_lists_four():
    langs = {item["language"] for item in list_supported_languages()}
    assert langs == {"python", "sql", "java", "r"}


def test_language_availability_flags():
    avail = {item["language"]: item["available"] for item in list_supported_languages()}
    assert avail["python"] is True
    assert avail["sql"] is True
    assert avail["java"] is False
    assert avail["r"] is False


def test_register_missing_name_raises(engine: MultiLanguageTransform):
    with pytest.raises(MultiLanguageError) as exc:
        engine.register("python", "def transform(rows):\n return rows", "")
    assert exc.value.code == "MISSING_NAME"


def test_register_unsupported_language_raises(engine: MultiLanguageTransform):
    with pytest.raises(MultiLanguageError) as exc:
        engine.register("ruby", "code", "x")
    assert exc.value.code == "UNSUPPORTED_LANGUAGE"


def test_python_register_and_invoke(engine: MultiLanguageTransform):
    code = "def transform(rows):\n    return [{**r, 'doubled': r.get('v', 0) * 2} for r in rows]"
    tf = engine.register("python", code, "double_it")
    result = engine.invoke(tf.id, [{"v": 1}, {"v": 2}])
    assert result == [{"v": 1, "doubled": 2}, {"v": 2, "doubled": 4}]


def test_sql_select_star(engine: MultiLanguageTransform):
    tf = engine.register("sql", "SELECT * FROM t", "all_rows")
    result = engine.invoke(tf.id, [{"a": 1}, {"a": 2}])
    assert result == [{"a": 1}, {"a": 2}]


def test_sql_select_columns(engine: MultiLanguageTransform):
    tf = engine.register("sql", "SELECT a, b FROM t", "cols")
    result = engine.invoke(tf.id, [{"a": 1, "b": 2, "c": 3}])
    assert result == [{"a": 1, "b": 2}]


def test_sql_where_filter(engine: MultiLanguageTransform):
    tf = engine.register("sql", "SELECT * FROM t WHERE age > 18", "adults")
    rows = [{"age": 10}, {"age": 20}, {"age": 30}]
    result = engine.invoke(tf.id, rows)
    assert [r["age"] for r in result] == [20, 30]


def test_sql_parse_error(engine: MultiLanguageTransform):
    tf = engine.register("sql", "DELETE FROM t", "bad")
    with pytest.raises(MultiLanguageError) as exc:
        engine.invoke(tf.id, [])
    assert exc.value.code == "SQL_PARSE_ERROR"


def test_java_registered_but_not_executable(engine: MultiLanguageTransform):
    tf = engine.register("java", "public class T {}", "jt")
    assert tf.available is False
    with pytest.raises(MultiLanguageError) as exc:
        engine.invoke(tf.id, [])
    assert exc.value.code == "NOT_IMPLEMENTED"


def test_r_registered_but_not_executable(engine: MultiLanguageTransform):
    tf = engine.register("r", "transform <- function(rows) rows", "rt")
    assert tf.available is False
    with pytest.raises(MultiLanguageError) as exc:
        engine.invoke(tf.id, [])
    assert exc.value.code == "NOT_IMPLEMENTED"
