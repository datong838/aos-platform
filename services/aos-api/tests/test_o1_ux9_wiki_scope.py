from __future__ import annotations

import uuid

from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.ecom_projector import PROJECTOR_ACTOR
from aos_api.routers.ontology import get_wiki, wiki_coverage_index


def test_product_wiki_coverage_only_counts_actually_listed_products_and_missing_is_a_gap() -> None:
    suffix = uuid.uuid4().hex
    org_id, project_id = f"org-{suffix}", f"project-{suffix}"
    principal = Principal(subject="ux9-wiki", org_id=org_id, project_id=project_id, roles=["admin"], markings=["public"])
    with connect() as conn:
        conn.execute("INSERT INTO twa_org (id,name) VALUES (%s,%s)", (org_id, org_id))
        conn.execute("INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s)", (org_id, project_id, project_id))
        conn.execute("INSERT INTO meta_object_type (id,name,description,published,properties) VALUES ('Product','商品','',true,'[]'::jsonb) ON CONFLICT DO NOTHING")
        conn.execute("SELECT set_config('aos.projection_actor', %s, true)", (PROJECTOR_ACTOR,))
        conn.execute(
            """
            INSERT INTO obj_instance (object_type,object_id,props,org_id,project_id) VALUES
              ('Product','niushop:1:listed','{"title":"已上架","status":"active","isDelete":"0","state":"1"}'::jsonb,%s,%s),
              ('Product','niushop:1:off','{"title":"已下架","status":"active","isDelete":"0","state":"0"}'::jsonb,%s,%s),
              ('Product','niushop:1:deleted','{"title":"已删除","status":"active","isDelete":"1","state":"1"}'::jsonb,%s,%s)
            """,
            (org_id, project_id, org_id, project_id, org_id, project_id),
        )
        conn.commit()
    try:
        coverage = wiki_coverage_index("Product", 50, principal)
        assert coverage["coverage"] == {"covered": 0, "gaps": 1, "visible": 1, "total": 1}
        assert [item["objectId"] for item in coverage["items"]] == ["niushop:1:listed"]
        assert coverage["items"][0]["displayLabel"] == "商品 · 已上架"
        missing = get_wiki("Product", "niushop:1:listed", True, principal)
        assert missing["exists"] is False
        assert missing["body"] == {}
    finally:
        with connect() as conn:
            conn.execute("SELECT set_config('aos.projection_actor', %s, true)", (PROJECTOR_ACTOR,))
            conn.execute("DELETE FROM obj_instance WHERE org_id=%s AND project_id=%s", (org_id, project_id))
            conn.execute("DELETE FROM twa_workspace WHERE org_id=%s AND project_id=%s", (org_id, project_id))
            conn.execute("DELETE FROM twa_org WHERE id=%s", (org_id,))
            conn.execute("DELETE FROM meta_object_type WHERE id='Product' AND NOT EXISTS (SELECT 1 FROM obj_instance WHERE object_type='Product')")
            conn.commit()
