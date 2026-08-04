from __future__ import annotations

import hashlib
import uuid

from aos_api.aip_kv_store import put_payload
from aos_api.db import connect
from aos_api.llm_provider_registry import (
    KEY_INSTALLS,
    install_plugin,
    list_llm_provider_plugins,
    plugins_root,
)
from aos_api.tenant_scope import TenantScope, bind_tenant_scope


def _workspace(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s) "
            "ON CONFLICT (org_id,project_id) DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.commit()


def _catalog(scope: TenantScope) -> dict:
    with bind_tenant_scope(scope):
        return list_llm_provider_plugins()


def test_disk_provider_template_is_shared_but_installation_is_scoped() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-template-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-template-b-{suffix}", f"project-b-{suffix}")
    _workspace(scope_a)
    _workspace(scope_b)

    manifest = plugins_root() / "moonshot" / "manifest.json"
    before_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    with bind_tenant_scope(scope_a):
        put_payload(KEY_INSTALLS, {"installed": []})
    with bind_tenant_scope(scope_b):
        put_payload(KEY_INSTALLS, {"installed": []})

    before_a = {item["id"]: item for item in _catalog(scope_a)["items"]}
    before_b = {item["id"]: item for item in _catalog(scope_b)["items"]}
    assert before_a["moonshot"]["version"] == before_b["moonshot"]["version"]
    assert before_a["moonshot"]["installed"] is False
    assert before_b["moonshot"]["installed"] is False

    with bind_tenant_scope(scope_a):
        install_plugin("moonshot")

    after_a = {item["id"]: item for item in _catalog(scope_a)["items"]}
    after_b = {item["id"]: item for item in _catalog(scope_b)["items"]}
    assert after_a["moonshot"]["installed"] is True
    assert after_b["moonshot"]["installed"] is False
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == before_hash

    for scope in (scope_a, scope_b):
        with connect(scope) as conn:
            conn.execute("DELETE FROM meta_aip_kv WHERE key=%s", (KEY_INSTALLS,))
            conn.commit()
