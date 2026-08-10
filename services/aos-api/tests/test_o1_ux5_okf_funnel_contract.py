from __future__ import annotations

import uuid

import pytest

from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.routers.ontology import (
    FunnelRerunIn,
    _OKF_DEFAULTS,
    funnel_rerun,
    funnel_status,
    get_okf_mapping,
    put_okf_mapping,
    wiki_coverage_index,
)


def _principal(org_id: str, project_id: str) -> Principal:
    return Principal(subject="o1-ux5-test", org_id=org_id, project_id=project_id, roles=["admin"], markings=["public"])


def _workspace(org_id: str, project_id: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING", (org_id, org_id))
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (org_id, project_id, project_id),
        )
        conn.commit()


def test_ecom_default_is_order_and_mapping_write_has_cas_revision() -> None:
    suffix = uuid.uuid4().hex
    scope = (f"org-{suffix}", f"project-{suffix}")
    _workspace(*scope)
    principal = _principal(*scope)
    try:
        default = get_okf_mapping("ecom", principal)
        assert _OKF_DEFAULTS["ecom_Order"]["objectType"] == "Order"
        assert default["objectType"] == "Order"
        assert default["revision"] == 0
        saved = put_okf_mapping("ecom", {**default, "expectedRevision": 0}, principal)
        assert saved["revision"] == 1
        assert saved["coverage"]["percent"] == 100
        assert get_okf_mapping("ecom", principal)["revision"] == 1
        with pytest.raises(ApiError) as stale:
            put_okf_mapping("ecom", {**default, "expectedRevision": 0}, principal)
        assert stale.value.code == "OKF_MAPPING_CAS_CONFLICT"
        assert stale.value.status_code == 412
    finally:
        with connect() as conn:
            conn.execute("DELETE FROM meta_aip_kv WHERE org_id=%s AND project_id=%s AND key='okf_mapping:ecom'", scope)
            conn.commit()


def test_funnel_rerun_receipt_is_persisted_and_read_back() -> None:
    suffix = uuid.uuid4().hex
    scope = (f"org-{suffix}", f"project-{suffix}")
    object_type = f"Order-{suffix}"
    _workspace(*scope)
    principal = _principal(*scope)
    try:
        result = funnel_rerun(object_type, FunnelRerunIn(mode="live"), principal)
        verified = funnel_status(object_type, principal)
        assert result["receiptId"]
        assert verified["detail"]["receiptId"] == result["receiptId"]
        assert verified["stage"] == result["stage"] == "hydration"
        assert verified["detail"]["failures"] == []
    finally:
        with connect() as conn:
            conn.execute("DELETE FROM funnel_status WHERE org_id=%s AND project_id=%s AND object_type=%s", (*scope, object_type))
            conn.commit()


def test_wiki_coverage_index_distinguishes_covered_subjects_and_gaps() -> None:
    suffix = uuid.uuid4().hex
    scope = (f"org-{suffix}", f"project-{suffix}")
    object_type = f"Coverage-{suffix}"
    _workspace(*scope)
    principal = _principal(*scope)
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type (id,name,description,published,properties,required_markings) VALUES (%s,%s,'',true,'[]'::jsonb,'[]'::jsonb)",
            (object_type, object_type),
        )
        conn.execute(
            "INSERT INTO obj_instance (object_type,object_id,props,org_id,project_id) VALUES (%s,'one','{}'::jsonb,%s,%s),(%s,'two','{}'::jsonb,%s,%s)",
            (object_type, *scope, object_type, *scope),
        )
        conn.execute(
            "INSERT INTO wiki_page (object_type,object_id,body,org_id,project_id) VALUES (%s,'one','{\"summary\":\"authoritative\"}'::jsonb,%s,%s)",
            (object_type, *scope),
        )
        conn.commit()
    try:
        result = wiki_coverage_index(object_type, 50, principal)
        assert result["coverage"] == {"covered": 1, "gaps": 1, "visible": 2, "total": 2}
        assert [(item["objectId"], item["covered"]) for item in result["items"]] == [("one", True), ("two", False)]
        assert result["items"][0]["summary"] == "authoritative"
    finally:
        with connect() as conn:
            conn.execute("DELETE FROM wiki_page WHERE org_id=%s AND project_id=%s AND object_type=%s", (*scope, object_type))
            conn.execute("DELETE FROM obj_instance WHERE org_id=%s AND project_id=%s AND object_type=%s", (*scope, object_type))
            conn.execute("DELETE FROM meta_object_type WHERE id=%s", (object_type,))
            conn.commit()
