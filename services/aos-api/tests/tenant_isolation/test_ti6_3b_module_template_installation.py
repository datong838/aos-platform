from __future__ import annotations

import uuid

from aos_api.db import connect
from aos_api.ecom_projector import PROJECTOR_ACTOR
from aos_api.module_store import (
    get_effective_module_config,
    get_module,
    install_module_template,
    module_etag,
    uninstall_module,
)
from aos_api.module_templates import (
    get_module_template,
    list_module_templates,
    template_view,
)
from aos_api.tenant_scope import TenantScope


def _prepare_scope(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES ('Order','Order') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO meta_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO meta_workspace (org_id,project_id,name,deletable,kind) "
            "VALUES (%s,%s,%s,true,'test') ON CONFLICT (org_id,project_id) DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name,deletable,kind) "
            "VALUES (%s,%s,%s,true,'test') ON CONFLICT (org_id,project_id) DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.commit()


def test_ti6_3b_catalog_contains_exact_four_immutable_templates(client) -> None:
    expected = {
        "workshop.order-management",
        "workshop.risk-inbox",
        "workshop.cop-dashboard",
        "workshop.buddy-assist",
    }
    first = list_module_templates()
    first[0]["name"] = "mutated-copy"
    second = list_module_templates()

    assert {item["templateId"] for item in second} == expected
    assert second[0]["name"] != "mutated-copy"
    assert all(item["baseContentHash"].startswith("sha256:") for item in second)

    unauthenticated = client.get("/v1/module-templates")
    assert unauthenticated.status_code == 401
    response = client.get(
        "/v1/module-templates",
        headers={
            "Authorization": "Bearer dev",
            "X-Org-Id": "dev-org",
            "X-Project-Id": "dev-project",
        },
    )
    assert response.status_code == 200
    assert {item["templateId"] for item in response.json()["items"]} == expected


def test_ti6_3b_same_template_has_scoped_overlay_and_uninstall(client) -> None:
    suffix = uuid.uuid4().hex[:12]
    scope_a = TenantScope(f"ti6-a-{suffix}", "workspace")
    scope_b = TenantScope(f"ti6-b-{suffix}", "workspace")
    _prepare_scope(scope_a)
    _prepare_scope(scope_b)

    installed_a = install_module_template(
        scope_a,
        template_id="workshop.order-management",
        overlay_patch={"brand": {"name": "A"}, "metrics": ["gmv"]},
        actor="owner-a",
    )
    installed_b = install_module_template(
        scope_b,
        template_id="workshop.order-management",
        overlay_patch={"brand": {"name": "B"}, "metrics": ["orders"]},
        actor="owner-b",
    )
    object_id = f"order-{suffix}"
    with connect(scope_a) as conn:
        # O1-UA2 owns compatibility-view writes through the single projector.
        # This fixture creates a projected business row so the uninstall test
        # continues to exercise the real post-O1 authority boundary.
        conn.execute("SELECT set_config('aos.projection_actor', %s, true)", (PROJECTOR_ACTOR,))
        conn.execute(
            "INSERT INTO obj_instance (object_type,object_id,props,org_id,project_id) "
            "VALUES ('Order',%s,'{\"status\":\"paid\"}'::jsonb,%s,%s)",
            (object_id, *scope_a.key),
        )
        conn.commit()
    with connect(scope_a) as conn:
        before_business = conn.execute(
            "SELECT md5(props::text) AS digest FROM obj_instance "
            "WHERE org_id=%s AND project_id=%s AND object_type='Order' AND object_id=%s",
            (*scope_a.key, object_id),
        ).fetchone()["digest"]

    assert installed_a["module"]["id"] == installed_b["module"]["id"]
    assert installed_a["overlay"]["effectiveConfigHash"] != installed_b["overlay"][
        "effectiveConfigHash"
    ]
    assert get_effective_module_config(scope_a, "mod-order-management")[
        "effectiveConfig"
    ]["brand"] == {"name": "A"}
    assert get_effective_module_config(scope_b, "mod-order-management")[
        "effectiveConfig"
    ]["brand"] == {"name": "B"}
    response = client.get(
        "/v1/modules/mod-order-management/effective-config",
        headers={
            "Authorization": "Bearer dev",
            "X-Org-Id": scope_a.org_id,
            "X-Project-Id": scope_a.project_id,
        },
    )
    assert response.status_code == 200
    assert response.json()["effectiveConfig"]["brand"] == {"name": "A"}

    module_a = get_module(scope_a, "mod-order-management")
    assert module_a is not None
    assert uninstall_module(
        scope_a, "mod-order-management", module_etag(module_a)
    ) == {"moduleId": "mod-order-management", "status": "uninstalled"}
    assert get_module(scope_a, "mod-order-management") is None
    assert get_module(scope_b, "mod-order-management") is not None
    with connect(scope_a) as conn:
        after_business = conn.execute(
            "SELECT md5(props::text) AS digest FROM obj_instance "
            "WHERE org_id=%s AND project_id=%s AND object_type='Order' AND object_id=%s",
            (*scope_a.key, object_id),
        ).fetchone()["digest"]
    assert after_business == before_business

    reinstalled = install_module_template(
        scope_a,
        template_id="workshop.order-management",
        overlay_patch={"brand": {"name": "A2"}},
        actor="owner-a",
    )
    assert reinstalled["overlay"]["revision"] == 2
    assert get_effective_module_config(scope_a, "mod-order-management")[
        "effectiveConfig"
    ]["brand"] == {"name": "A2"}


def test_ti6_3b_overlay_rejects_unfrozen_keys() -> None:
    template = get_module_template("workshop.order-management")
    assert template is not None
    view = template_view(template)
    assert view["baseContentHash"].startswith("sha256:")

    scope = TenantScope(f"ti6-invalid-{uuid.uuid4().hex[:12]}", "workspace")
    _prepare_scope(scope)
    try:
        install_module_template(
            scope,
            template_id="workshop.order-management",
            overlay_patch={"tenantScope": "override"},
            actor="owner",
        )
    except ValueError as exc:
        assert "unsupported overlay keys" in str(exc)
    else:
        raise AssertionError("unsupported overlay key must fail closed")
