from __future__ import annotations

import pytest

from aos_api.errors import ApiError
from aos_api.routers.ontology import _resolve_object_sort, _sort_object_items


def test_order_defaults_to_real_created_at_desc_with_stable_object_id() -> None:
    sort = _resolve_object_sort("Order", None, None)
    assert sort == ("createdAt", "desc")

    items = [
        {"id": "niushop:1:2", "createdAt": "2026-01-24T13:12:00Z"},
        {"id": "niushop:1:20", "createdAt": "2026-03-07T15:22:00Z"},
        {"id": "niushop:1:21", "createdAt": "2026-03-07T15:22:00Z"},
        {"id": "niushop:1:bad", "createdAt": "not-a-time"},
    ]

    ordered, invalid_count = _sort_object_items(items, sort)

    assert [item["id"] for item in ordered] == [
        "niushop:1:21",
        "niushop:1:20",
        "niushop:1:2",
        "niushop:1:bad",
    ]
    assert invalid_count == 1


def test_unknown_sort_field_fails_closed() -> None:
    with pytest.raises(ApiError) as exc:
        _resolve_object_sort("Order", "totalAmount", "desc")
    assert exc.value.code == "OBJECT_SORT_INVALID"
    assert exc.value.status_code == 422


def test_non_order_keeps_canonical_order_without_explicit_sort() -> None:
    assert _resolve_object_sort("Product", None, None) is None
    items = [{"id": "b"}, {"id": "a"}]
    ordered, invalid_count = _sort_object_items(items, None)
    assert ordered == items
    assert invalid_count == 0
