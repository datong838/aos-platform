from __future__ import annotations


def test_memory_catalog_never_touches_shared_postgres(monkeypatch):
    from aos_api import membership, orgs, tenant_catalog, twa_pg, workspaces_catalog

    monkeypatch.setenv("AOS_TWA_STORE", "memory")
    twa_pg.clear_mode_cache()
    orgs.reset_org_store()
    workspaces_catalog.reset_workspace_catalog()
    membership.reset_membership_store()

    def forbidden_connect():
        raise AssertionError("memory tenant catalog must not connect to PostgreSQL")

    monkeypatch.setattr(tenant_catalog, "connect", forbidden_connect)
    monkeypatch.setattr(orgs, "connect", forbidden_connect)
    monkeypatch.setattr(workspaces_catalog, "connect", forbidden_connect)
    monkeypatch.setattr(membership, "connect", forbidden_connect)
    orgs.ensure_org("org-test", name="测试组织")
    workspaces_catalog.ensure_workspace("org-test", "ws-test", name="测试工作区")
    membership.upsert_member(
        "org-test", "ws-test", "alice", "owner", actor_id="alice"
    )

    assert orgs.get_org("org-test") is not None
    assert workspaces_catalog.get_workspace("org-test", "ws-test") is not None
    assert membership.is_member("org-test", "ws-test", "alice")
    orgs.reset_org_store()
    workspaces_catalog.reset_workspace_catalog()
    membership.reset_membership_store()


def test_memory_catalog_boot_preserves_seeded_state(monkeypatch):
    from aos_api import orgs, twa_pg
    from aos_api.tenant_catalog import boot_tenant_catalogs

    monkeypatch.setenv("AOS_TWA_STORE", "memory")
    twa_pg.clear_mode_cache()
    orgs.reset_org_store()
    orgs.ensure_org("org-test", name="测试组织")

    boot_tenant_catalogs()

    assert orgs.get_org("org-test") == {
        "id": "org-test",
        "name": "测试组织",
        "kind": "standard",
        "joinPolicy": "invite_or_apply",
        "discoverable": True,
    }
    orgs.reset_org_store()
