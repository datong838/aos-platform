"""Phase 4 · Ontology Wikis — 单元测试 (≥5)."""
from __future__ import annotations

import pytest

from aos_api.ontology_wiki_engine import get_wiki_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_wiki_engine().reset()
    yield


def test_create_and_get_wiki() -> None:
    eng = get_wiki_engine()
    w = eng.create_wiki(title="Hello", content="body", tags=["a"])
    fetched = eng.get_wiki(w.id)
    assert fetched is not None
    assert fetched.title == "Hello"
    assert fetched.version == 1  # 初始版本


def test_list_wikis_search() -> None:
    eng = get_wiki_engine()
    eng.create_wiki(title="Alpha Guide", content="x")
    eng.create_wiki(title="Beta Notes", content="y")
    items = eng.list_wikis(search="alph")
    assert len(items) == 1
    assert items[0].title == "Alpha Guide"


def test_list_wikis_tag_filter() -> None:
    eng = get_wiki_engine()
    eng.create_wiki(title="A", content="x", tags=["customer"])
    eng.create_wiki(title="B", content="y", tags=["order"])
    items = eng.list_wikis(tag="order")
    assert len(items) == 1
    assert items[0].title == "B"


def test_update_creates_new_version() -> None:
    eng = get_wiki_engine()
    w = eng.create_wiki(title="V1", content="c1")
    updated = eng.update_wiki(w.id, content="c2", message="second")
    assert updated.version == 2
    versions = eng.list_versions(w.id)
    assert len(versions) == 2
    assert versions[1].content == "c2"


def test_diff_versions() -> None:
    eng = get_wiki_engine()
    w = eng.create_wiki(title="T", content="line1\nline2")
    eng.update_wiki(w.id, content="line1\nline2\nline3", message="add line3")
    d = eng.diff(w.id, 1, 2)
    assert d["from_version"] == 1
    assert d["to_version"] == 2
    assert d["added_count"] >= 1
    assert "line3" in d["added_lines"]


def test_delete_wiki() -> None:
    eng = get_wiki_engine()
    w = eng.create_wiki(title="Tmp")
    assert eng.delete_wiki(w.id) is True
    assert eng.get_wiki(w.id) is None
    # 版本也被清除
    assert eng.list_versions(w.id) == []


def test_get_version_not_found() -> None:
    eng = get_wiki_engine()
    w = eng.create_wiki(title="T", content="c")
    assert eng.get_version(w.id, 999) is None
