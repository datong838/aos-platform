"""Phase 3 · AIP Assist — 单元测试。"""
import json
import pytest

from aos_api.aip_assist_engine import get_engine, AssistEngine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def test_welcome():
    eng = get_engine()
    result = eng.get_welcome(role="admin")
    assert "message" in result
    assert result["role"] == "admin"
    assert "config" in result["tags"]
    assert "deploy" in result["tags"]


def test_welcome_role_tags():
    eng = get_engine()
    viewer_tags = eng.get_welcome(role="viewer")["tags"]
    assert "faq" in viewer_tags
    assert "deploy" not in viewer_tags


def test_list_suggestions():
    eng = get_engine()
    items = eng.list_suggestions()
    assert len(items) >= 12
    assert all("category" in s and "text" in s for s in items)


def test_suggestions_filter_by_category():
    eng = get_engine()
    data_sugs = eng.list_suggestions(category="data")
    assert len(data_sugs) >= 2
    assert all(s["category"] == "data" for s in data_sugs)


def test_add_suggestion():
    eng = get_engine()
    before = len(eng.list_suggestions())
    item = eng.add_suggestion("custom", "自定义建议")
    assert item["text"] == "自定义建议"
    assert item["category"] == "custom"
    assert len(eng.list_suggestions()) == before + 1


def test_create_conversation():
    eng = get_engine()
    conv = eng.create_conversation(title="Test")
    assert conv.title == "Test"
    fetched = eng.get_conversation(conv.id)
    assert fetched is not None
    assert fetched.id == conv.id


def test_add_message():
    eng = get_engine()
    conv = eng.create_conversation("Msg Test")
    msg = eng.add_message(conv.id, "user", "Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    fetched = eng.get_conversation(conv.id)
    assert len(fetched.messages) == 1


def test_list_conversations():
    eng = get_engine()
    eng.create_conversation("C1")
    eng.create_conversation("C2")
    convs = eng.list_conversations()
    assert len(convs) == 2


def test_delete_conversation():
    eng = get_engine()
    conv = eng.create_conversation("ToDelete")
    assert eng.delete_conversation(conv.id) is True
    assert eng.get_conversation(conv.id) is None
    assert eng.delete_conversation("fake") is False


def test_generate_reply_tokens():
    eng = get_engine()
    tokens = eng.generate_reply_tokens("test input")
    assert len(tokens) > 0
    assert all(isinstance(t, str) for t in tokens)


def test_add_message_nonexistent():
    eng = get_engine()
    with pytest.raises(KeyError):
        eng.add_message("nonexistent", "user", "text")


def test_singleton():
    e1 = get_engine()
    e2 = AssistEngine()
    assert e1 is e2
