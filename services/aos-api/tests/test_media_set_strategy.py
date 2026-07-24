"""W2-#1 · 媒体集延迟策略测试。"""
from __future__ import annotations

import pytest

from aos_api.media_reference import MediaReference, MediaReferenceStore
from aos_api.media_set import LOAD_STRATEGIES, MediaSetError, MediaSetStore


@pytest.fixture
def setup_store():
    ref_store = MediaReferenceStore()
    r1 = ref_store.register(kind="image", storage="local", bucket="test", path="a.png", size_bytes=100)
    r2 = ref_store.register(kind="image", storage="local", bucket="test", path="b.png", size_bytes=200)
    import aos_api.media_set as ms_mod
    orig_get = ms_mod.get_media_store
    ms_mod.get_media_store = lambda: ref_store
    store = MediaSetStore()
    yield store, r1.id, r2.id
    ms_mod.get_media_store = orig_get


def test_load_strategies_constant():
    assert LOAD_STRATEGIES == ("lazy", "eager", "stream")


def test_create_with_eager_strategy(setup_store):
    store, r1, _ = setup_store
    ms = store.create("img", "image", load_strategy="eager")
    assert ms.load_strategy == "eager"


def test_create_with_lazy_strategy(setup_store):
    store, _, _ = setup_store
    ms = store.create("img", "image", load_strategy="lazy")
    assert ms.load_strategy == "lazy"


def test_create_with_stream_strategy(setup_store):
    store, _, _ = setup_store
    ms = store.create("img", "image", load_strategy="stream")
    assert ms.load_strategy == "stream"


def test_create_default_strategy_is_eager(setup_store):
    store, _, _ = setup_store
    ms = store.create("img", "image")
    assert ms.load_strategy == "eager"


def test_create_bad_strategy_raises(setup_store):
    store, _, _ = setup_store
    with pytest.raises(MediaSetError) as exc:
        store.create("img", "image", load_strategy="bogus")
    assert exc.value.code == "BAD_STRATEGY"


def test_get_rows_eager_returns_list(setup_store):
    store, r1, r2 = setup_store
    ms = store.create("img", "image", load_strategy="eager")
    store.add_media(ms.id, r1)
    store.add_media(ms.id, r2)
    rows = store.get_rows(ms.id)
    assert len(rows) == 2
    assert all("media_ref_id" in r for r in rows)


def test_get_rows_lazy_returns_paginated(setup_store):
    store, r1, r2 = setup_store
    ms = store.create("img", "image", load_strategy="lazy")
    store.add_media(ms.id, r1)
    store.add_media(ms.id, r2)
    result = store.get_rows_lazy(ms.id, page=1, page_size=1)
    assert result["total"] == 2
    assert len(result["rows"]) == 1
    assert result["has_more"] is True
    page2 = store.get_rows_lazy(ms.id, page=2, page_size=1)
    assert page2["has_more"] is False


def test_get_rows_stream_yields_rows(setup_store):
    store, r1, r2 = setup_store
    ms = store.create("img", "image", load_strategy="stream")
    store.add_media(ms.id, r1)
    store.add_media(ms.id, r2)
    rows = list(store.get_rows_stream(ms.id))
    assert len(rows) == 2


def test_get_rows_with_override_strategy(setup_store):
    store, r1, _ = setup_store
    ms = store.create("img", "image", load_strategy="lazy")
    store.add_media(ms.id, r1)
    rows = store.get_rows(ms.id, strategy="eager")
    assert len(rows) == 1
