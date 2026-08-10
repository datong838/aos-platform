from __future__ import annotations

import json
import uuid

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


def _headers(org_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_id,
        "X-Project-Id": "dev-project",
        "X-Trace-Id": f"aip0-canary-{org_id}",
    }


def test_aip_draft_reads_are_auth_bound_and_cross_tenant_fail_closed(client):
    """AIP-0 canary: same draft id is never visible outside its auth scope."""
    org_id = "org-org"
    project_id = "dev-project"
    draft_id = f"aip0-{uuid.uuid4().hex[:12]}"

    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (org_id, "栖月汇商贸有限公司"),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s) "
            "ON CONFLICT (org_id,project_id) DO NOTHING",
            (org_id, project_id, "默认工作区"),
        )
        conn.commit()

    with connect(TenantScope(org_id, project_id)) as conn:
        conn.execute(
            """
            INSERT INTO draft_dataset
              (id, action_type_id, object_type, object_id, title, proposed, status,
               created_by, org_id, project_id)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,'proposed',%s,%s,%s)
            """,
            (
                draft_id,
                "aip0_canary",
                "Order",
                "canary-order",
                "AIP-0 tenant canary",
                json.dumps({"canary": True}),
                "test:aip0",
                org_id,
                project_id,
            ),
        )
        conn.commit()

    assert client.get(f"/v1/aip/drafts/{draft_id}").status_code == 401

    owner = client.get(f"/v1/aip/drafts/{draft_id}", headers=_headers(org_id))
    assert owner.status_code == 200
    assert owner.json()["id"] == draft_id

    cross_tenant = client.get(
        f"/v1/aip/drafts/{draft_id}", headers=_headers("dev-org")
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["code"] == "NOT_FOUND"

    cross_list = client.get("/v1/aip/drafts", headers=_headers("dev-org"))
    assert cross_list.status_code == 200
    assert draft_id not in {item["id"] for item in cross_list.json()["items"]}
