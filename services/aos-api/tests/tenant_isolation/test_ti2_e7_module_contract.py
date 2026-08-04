from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from aos_api.canvas_config import get_config, put_config
from aos_api.db import connect
from aos_api.module_events import create_event, get_event
from aos_api.module_interfaces import get_interface, put_interface
from aos_api.module_queries import create_query, get_query
from aos_api.module_store import create_module, get_module
from aos_api.module_variables import create_variable, get_variable
from aos_api.tenant_schema_lint import build_ti2_e7_schema_report
from aos_api.tenant_scope import TenantScope
from aos_api.widget_instances import create_instance, get_instance

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti2e7_module_contract.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("ti2e7_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_migration_is_scoped_and_reversible() -> None:
    module = _load_migration()
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti2e7contract"
    assert module.down_revision == "228ti2e6rls"
    assert "module_event_orphan_quarantine" in source
    assert "REVOKE ALL" in source
    assert "ALTER COLUMN module_pk SET NOT NULL" in source
    assert "ALTER COLUMN module_id SET NOT NULL" in source
    assert "PRIMARY KEY (org_id, project_id, module_pk)" in source
    assert "PRIMARY KEY (org_id, project_id, id)" in source
    assert "downgrade blocked by legacy key collision" in source


def test_e7_schema_report_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti2_e7_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti2e7contract",
        "228ti3e1expand",
        "228ti3e4validate",
        "228ti3e6rls",
        "228ti3e7contract",
        "228ti4c1expand",
        "228ti4d1expand",
    }
    assert report["ti2ContractInvalidPrimaryKeys"] == []
    assert report["ti2ContractNullableModulePkTables"] == []
    assert report["ti2OrphanQuarantineExists"] is True
    assert report["ti2ActiveNullModulePkEventCount"] == 0
    assert report["ti2RuntimeQuarantineAccess"] is False


def test_app04_same_module_and_child_ids_coexist_across_scopes(client) -> None:
    suffix = uuid.uuid4().hex
    module_id = f"shared-module-{suffix}"
    child_id = f"shared-child-{suffix}"
    scope_a = TenantScope(f"org-a-{suffix}", f"project-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-{suffix}")

    create_module(scope_a, {"id": module_id, "name": "A"})
    create_module(scope_b, {"id": module_id, "name": "B"})
    put_config(scope_a, module_id, {"owner": "A"}, {})
    put_config(scope_b, module_id, {"owner": "B"}, {})
    put_interface(scope_a, module_id, {"name": "API-A"})
    put_interface(scope_b, module_id, {"name": "API-B"})
    create_instance(scope_a, module_id, {"id": child_id, "title": "A"})
    create_instance(scope_b, module_id, {"id": child_id, "title": "B"})
    create_variable(scope_a, module_id, {"id": child_id, "name": "A"})
    create_variable(scope_b, module_id, {"id": child_id, "name": "B"})
    create_query(scope_a, module_id, {"id": child_id, "name": "A"})
    create_query(scope_b, module_id, {"id": child_id, "name": "B"})
    create_event(scope_a, module_id, {"id": child_id, "name": "A"})
    create_event(scope_b, module_id, {"id": child_id, "name": "B"})

    assert get_module(scope_a, module_id)["name"] == "A"
    assert get_module(scope_b, module_id)["name"] == "B"
    assert get_config(scope_a, module_id)["layout"] == {"owner": "A"}
    assert get_config(scope_b, module_id)["layout"] == {"owner": "B"}
    assert get_interface(scope_a, module_id)["name"] == "API-A"
    assert get_interface(scope_b, module_id)["name"] == "API-B"
    assert get_instance(scope_a, module_id, child_id)["title"] == "A"
    assert get_instance(scope_b, module_id, child_id)["title"] == "B"
    assert get_variable(scope_a, module_id, child_id)["name"] == "A"
    assert get_variable(scope_b, module_id, child_id)["name"] == "B"
    assert get_query(scope_a, module_id, child_id)["name"] == "A"
    assert get_query(scope_b, module_id, child_id)["name"] == "B"
    assert get_event(scope_a, module_id, child_id)["name"] == "A"
    assert get_event(scope_b, module_id, child_id)["name"] == "B"


def test_app05_uninstall_is_scoped_etag_guarded_and_keeps_business_data(client) -> None:
    suffix = uuid.uuid4().hex
    module_id = f"uninstall-module-{suffix}"
    scope_a = TenantScope(f"org-a-{suffix}", f"project-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-{suffix}")
    create_module(scope_a, {"id": module_id, "name": "A"})
    create_module(scope_b, {"id": module_id, "name": "B"})
    event = create_event(scope_a, module_id, {"name": "running"})

    headers_a = {
        "Authorization": "Bearer dev",
        "X-Org-Id": scope_a.org_id,
        "X-Project-Id": scope_a.project_id,
    }
    headers_b = {
        "Authorization": "Bearer dev",
        "X-Org-Id": scope_b.org_id,
        "X-Project-Id": scope_b.project_id,
    }
    with connect() as conn:
        before = conn.execute("SELECT COUNT(*) AS n FROM obj_instance").fetchone()["n"]

    current = client.get(f"/v1/modules/{module_id}", headers=headers_a)
    assert current.status_code == 200
    etag = current.headers["etag"]
    assert client.delete(f"/v1/modules/{module_id}", headers=headers_a).status_code == 428
    assert client.delete(
        f"/v1/modules/{module_id}", headers={**headers_a, "If-Match": '"stale"'}
    ).status_code == 412
    deleted = client.delete(
        f"/v1/modules/{module_id}", headers={**headers_a, "If-Match": etag}
    )
    assert deleted.status_code == 200
    assert client.get(f"/v1/modules/{module_id}", headers=headers_a).status_code == 404
    assert client.get(f"/v1/modules/{module_id}", headers=headers_b).status_code == 200

    with connect() as conn:
        after = conn.execute("SELECT COUNT(*) AS n FROM obj_instance").fetchone()["n"]
        enabled = conn.execute(
            "SELECT enabled FROM module_events WHERE id=%s AND org_id=%s AND project_id=%s",
            (event["id"], *scope_a.key),
        ).fetchone()["enabled"]
    assert before == after
    assert enabled is False
