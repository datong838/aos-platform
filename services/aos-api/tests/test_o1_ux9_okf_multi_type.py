from __future__ import annotations

import uuid

from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.routers.ontology import (
    get_okf_mapping,
    get_okf_mapping_types,
    get_okf_type_mapping,
    put_okf_type_mapping,
)


def _principal(org_id: str, project_id: str) -> Principal:
    return Principal(
        subject="o1-ux9-okf",
        org_id=org_id,
        project_id=project_id,
        roles=["admin"],
        markings=["public"],
    )


def _workspace(org_id: str, project_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (org_id, org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (org_id, project_id, project_id),
        )
        conn.commit()


def _source_object(org_id: str, project_id: str, object_type: str, external_id: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ecom_object (
              org_id,workspace_id,platform,shop_or_marketplace_id,object_type,external_id,
              properties,source_updated_at,source_timezone,canonical_status,raw_status,
              schema_version,payload_hash
            ) VALUES (%s,%s,'niushop','1',%s,%s,'{}'::jsonb,NOW(),'Z','active','',1,%s)
            """,
            (org_id, project_id, object_type, external_id, "0" * 64),
        )
        conn.commit()


def test_ecom_overview_all_types_have_defaults_and_full_required_coverage() -> None:
    """After D2.9 OKF defaults, every OT has a built-in mapping derived from
    ec_normalizer.py, giving 100% required coverage on first read."""
    suffix = uuid.uuid4().hex
    scope = (f"org-{suffix}", f"project-{suffix}")
    _workspace(*scope)
    principal = _principal(*scope)
    _source_object(*scope, "Order", "order-1")
    _source_object(*scope, "Product", "product-1")
    try:
        overview = get_okf_mapping_types("ecom", principal)
        assert [item["objectType"] for item in overview["items"]] == ["Order", "Product"]
        # Both OTs have defaults → 100% required coverage
        assert overview["overall"]["required"]["mapped"] == 12
        assert overview["overall"]["required"]["total"] == 12
        assert overview["overall"]["required"]["percent"] == 100
        assert overview["overall"]["complete"] is True
        assert overview["overall"]["unknown"] == []
        product = next(item for item in overview["items"] if item["objectType"] == "Product")
        assert product["status"] == "configured"
        assert product["source"]["count"] == 1
        assert product["coverage"]["required"] == {"mapped": 6, "total": 6, "percent": 100}
    finally:
        with connect() as conn:
            conn.execute("DELETE FROM ecom_object WHERE org_id=%s AND workspace_id=%s", scope)
            conn.commit()


def test_per_type_cas_storage_does_not_overwrite_legacy_order_mapping() -> None:
    suffix = uuid.uuid4().hex
    scope = (f"org-{suffix}", f"project-{suffix}")
    _workspace(*scope)
    principal = _principal(*scope)
    try:
        legacy_before = get_okf_mapping("ecom", principal)
        product_before = get_okf_type_mapping("ecom", "Product", principal)
        # Product now has a built-in default mapping (configured, revision=0)
        assert product_before["status"] == "configured"
        assert product_before["revision"] == 0
        saved = put_okf_type_mapping(
            "ecom",
            "Product",
            {
                "expectedRevision": 0,
                "label": "微商城电商 · Product",
                "columns": [
                    {"src": "goods_name", "dst": "Product.title", "ok": True},
                    {"src": "status", "dst": "Product.status", "ok": True},
                ],
            },
            principal,
        )
        assert saved["revision"] == 1
        assert saved["coverage"]["required"]["mapped"] == 2
        assert get_okf_type_mapping("ecom", "Product", principal)["revision"] == 1
        assert get_okf_mapping("ecom", principal)["revision"] == legacy_before["revision"]
    finally:
        with connect() as conn:
            conn.execute(
                "DELETE FROM meta_aip_kv WHERE org_id=%s AND project_id=%s AND key LIKE 'okf_mapping:ecom%%'",
                scope,
            )
            conn.commit()
