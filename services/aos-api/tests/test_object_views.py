"""W2-#13 · Object Views 微件系统测试。"""
from __future__ import annotations

import pytest

from aos_api.object_views import (
    WIDGET_CATALOG,
    ObjectView,
    ObjectViewError,
    ObjectViewStore,
    ViewWidget,
    list_widget_catalog,
)


@pytest.fixture
def store() -> ObjectViewStore:
    return ObjectViewStore()


def test_widget_catalog_has_twelve_kinds():
    catalog = list_widget_catalog()
    assert len(catalog) == 12
    kinds = {item["kind"] for item in catalog}
    assert "property_table" in kinds
    assert "rich_text" in kinds


def test_create_view(store: ObjectViewStore):
    view = ObjectView(name="订单视图", otd_id="otd-1")
    created = store.create(view)
    assert created.id in {v.id for v in store.list_all()}


def test_create_view_missing_name_raises(store: ObjectViewStore):
    with pytest.raises(ObjectViewError) as exc:
        store.create(ObjectView(name="", otd_id="otd-1"))
    assert exc.value.code == "MISSING_NAME"


def test_create_view_missing_otd_raises(store: ObjectViewStore):
    with pytest.raises(ObjectViewError) as exc:
        store.create(ObjectView(name="v", otd_id=""))
    assert exc.value.code == "MISSING_OTD"


def test_unknown_widget_kind_raises(store: ObjectViewStore):
    widget = ViewWidget.model_construct(kind="bogus_widget")
    with pytest.raises(ObjectViewError) as exc:
        store.create(ObjectView(name="v", otd_id="otd-1", widgets=[widget]))
    assert exc.value.code == "UNKNOWN_WIDGET"


def test_default_view_clears_previous_default(store: ObjectViewStore):
    store.create(ObjectView(name="v1", otd_id="otd-1", is_default=True))
    store.create(ObjectView(name="v2", otd_id="otd-1", is_default=True))
    defaults = [v for v in store.list_by_otd("otd-1") if v.is_default]
    assert len(defaults) == 1
    assert defaults[0].name == "v2"


def test_list_by_otd(store: ObjectViewStore):
    store.create(ObjectView(name="a", otd_id="otd-1"))
    store.create(ObjectView(name="b", otd_id="otd-2"))
    result = store.list_by_otd("otd-1")
    assert len(result) == 1
    assert result[0].name == "a"


def test_reorder_widgets(store: ObjectViewStore):
    w1 = ViewWidget(kind="property_table", title="w1")
    w2 = ViewWidget(kind="bar_chart", title="w2")
    view = store.create(ObjectView(name="v", otd_id="otd-1", widgets=[w1, w2]))
    reordered = store.reorder_widgets(view.id, [w2.id, w1.id])
    assert [w.title for w in reordered.widgets] == ["w2", "w1"]


def test_reorder_mismatch_raises(store: ObjectViewStore):
    view = store.create(ObjectView(name="v", otd_id="otd-1"))
    with pytest.raises(ObjectViewError) as exc:
        store.reorder_widgets(view.id, ["ghost"])
    assert exc.value.code == "REORDER_MISMATCH"


def test_add_and_remove_widget(store: ObjectViewStore):
    view = store.create(ObjectView(name="v", otd_id="otd-1"))
    widget = ViewWidget(kind="timeline", title="事件")
    updated = store.add_widget(view.id, widget)
    assert len(updated.widgets) == 1
    after_remove = store.remove_widget(view.id, widget.id)
    assert after_remove.widgets == []


def test_update_view(store: ObjectViewStore):
    view = store.create(ObjectView(name="v", otd_id="otd-1"))
    updated = store.update(view.id, name="新名称", is_default=True)
    assert updated.name == "新名称"
    assert updated.is_default is True


def test_delete_view(store: ObjectViewStore):
    view = store.create(ObjectView(name="v", otd_id="otd-1"))
    assert store.delete(view.id) is True
    assert store.get(view.id) is None
    assert store.delete(view.id) is False
