"""Canonical TenantScope binding for asset-control PostgreSQL transactions."""
from __future__ import annotations

from typing import Any

import psycopg

from aos_api.tenant_scope import TenantScope, apply_transaction_scope


def apply_asset_transaction_scope(
    conn: Any, *, org_id: str, project_id: str
) -> None:
    """Bind real psycopg connections; lightweight unit fakes have no RLS layer."""
    if isinstance(conn, psycopg.Connection):
        # Asset-store unit fixtures intentionally build earlier migration
        # snapshots in isolated schemas.  Activate the runtime role only after
        # the current schema has adopted the TI6 asset-control RLS contract.
        adopted = conn.execute(
            "SELECT 1 FROM pg_policies "
            "WHERE schemaname=current_schema() "
            "AND policyname='tenant_scope_bundle_composition_ti6'"
        ).fetchone()
        if adopted is None:
            return
        search_path = str(conn.execute("SHOW search_path").fetchone()["search_path"])
        apply_transaction_scope(conn, TenantScope(org_id, project_id))
        # SET ROLE may activate a role-specific default and hide isolated test
        # schemas; retain the caller transaction's already-resolved path.
        conn.execute("SELECT set_config('search_path', %s, true)", (search_path,))
