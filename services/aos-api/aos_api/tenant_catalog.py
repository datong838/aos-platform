"""Boot / schema for Org · Workspace · Membership persistence (164 v1.1)."""
from __future__ import annotations

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.tenant-catalog")

_schema_ready = False


def ensure_tenant_catalog_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_org (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              kind TEXT NOT NULL DEFAULT 'standard',
              join_policy TEXT NOT NULL DEFAULT 'invite_or_apply',
              discoverable BOOLEAN NOT NULL DEFAULT TRUE,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_workspace (
              org_id TEXT NOT NULL,
              project_id TEXT NOT NULL,
              name TEXT NOT NULL,
              deletable BOOLEAN NOT NULL DEFAULT TRUE,
              kind TEXT NOT NULL DEFAULT 'custom',
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY (org_id, project_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_membership (
              org_id TEXT NOT NULL,
              project_id TEXT NOT NULL,
              subject TEXT NOT NULL,
              role TEXT NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY (org_id, project_id, subject)
            )
            """
        )
        conn.commit()
    _schema_ready = True
    log.info("tenant_catalog_schema_ready")


def boot_tenant_catalogs() -> None:
    """Load PG → memory, then upsert Dev seeds (do not wipe user orgs)."""
    ensure_tenant_catalog_schema()
    from aos_api import membership as mem
    from aos_api import orgs as org_store
    from aos_api import workspaces_catalog as ws_cat

    org_store.load_orgs_from_db()
    ws_cat.load_workspaces_from_db()
    mem.load_memberships_from_db()
    org_store.seed_dev_orgs()
    ws_cat.seed_dev_workspaces()
    mem.seed_dev_defaults(reset_persons=False)
    log.info(
        "tenant_catalog_booted orgs=%s workspaces=%s members=%s",
        org_store.org_count(),
        ws_cat.workspace_count(),
        mem.membership_count(),
    )
