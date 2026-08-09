from __future__ import annotations

from aos_api.auth import Principal
from aos_api.routers.analytics import _list_objects_table


def test_analytics_object_list_reuses_ecommerce_pii_redaction(monkeypatch) -> None:
    from aos_api import marking
    from aos_api.routers import object_sets

    monkeypatch.setattr(
        object_sets,
        "_query_pg",
        lambda **_kwargs: {
            "items": [{
                "id": "wo-private", "mobile": "13800138000",
                "weapp_openid": "openid-private", "buyer_ip": "127.0.0.1",
                "title": "safe title",
            }],
            "total": 1, "source": "pg",
        },
    )
    monkeypatch.setattr(object_sets, "_prop_defs", lambda _object_type: [])
    monkeypatch.setattr(marking, "can_access_object", lambda *_args, **_kwargs: True)
    principal = Principal(subject="user:test", org_id="dev-org", project_id="dev-project")

    result = _list_objects_table(principal, "WorkOrder", limit=1)

    row = result["rows"][0]
    assert row["title"] == "safe title"
    assert row["mobile"] == "[REDACTED]"
    assert row["weapp_openid"] == "[REDACTED]"
    assert row["buyer_ip"] == "[REDACTED]"
    assert row["_redactedFields"] == ["buyer_ip", "mobile", "weapp_openid"]
