#!/usr/bin/env python3
"""Read-only effective-privilege inventory; no credential values or table data."""

from __future__ import annotations

from contextlib import contextmanager
import json

from a0v_formal_text_model_renewal import database_connect

TABLES = (
    "meta_action_type", "meta_object_type", "aip_action_proposal",
    "aip_action_draft", "aip_action_approval_event", "aip_action_draft_head",
    "aip_action_draft_revision", "aip_action_draft_command",
    "meta_membership", "authz_tuple", "aip_action_risk_policy",
)


@contextmanager
def head_action_connection(scope):
    from aos_api.tenant_scope import TenantScope, apply_transaction_scope
    if type(scope) is not TenantScope or scope.key != ("org-org", "dev-project"):
        raise ValueError("W5C3PR_EXACT_TENANT_REQUIRED")
    with database_connect("aos_meta_head")() as conn:
        apply_transaction_scope(conn, scope)
        state = conn.execute("""SELECT current_database() AS database_name,
          current_user AS role_name""").fetchone()
        if state != {"database_name": "aos_meta_head", "role_name": "aos_runtime"}:
            raise ValueError("W5C3PR_SCOPED_HEAD_CONNECTION_REQUIRED")
        yield conn


def inventory():
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = [dict(row) for row in conn.execute("""SELECT n.name,
          has_table_privilege('aos_runtime',n.name,'SELECT') AS can_select,
          has_table_privilege('aos_runtime',n.name,'INSERT') AS can_insert,
          has_table_privilege('aos_runtime',n.name,'UPDATE') AS can_update
          FROM unnest(%s::text[]) AS n(name)
          WHERE to_regclass('public.'||n.name) IS NOT NULL ORDER BY n.name""",
          (list(TABLES),)).fetchall()]
        role = dict(conn.execute("""SELECT rolcanlogin,rolsuper,rolbypassrls,
          rolinherit FROM pg_roles WHERE rolname='aos_runtime'""").fetchone())
        head = dict(conn.execute("""SELECT current_database() AS database_name,
          current_user AS role_name, inet_server_port() AS server_port""").fetchone())
    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope
    with connect(TenantScope("org-org", "dev-project")) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        app = dict(conn.execute("""SELECT current_database() AS database_name,
          current_user AS role_name, inet_server_port() AS server_port,
          to_regclass('public.meta_action_type') IS NOT NULL AS has_action_type,
          to_regclass('public.aip_action_proposal') IS NOT NULL AS has_proposal""").fetchone())
    from aos_api.tenant_scope import apply_transaction_scope
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        apply_transaction_scope(conn, TenantScope("org-org", "dev-project"))
        scoped = dict(conn.execute("""SELECT current_user AS role_name,
          has_table_privilege(current_user,'public.meta_action_type','SELECT') AS action_type_select,
          has_table_privilege(current_user,'public.aip_action_proposal','INSERT') AS proposal_insert,
          (SELECT count(*) FROM meta_action_type
           WHERE id='ecommerce_growth_cutover') AS cutover_action_types""").fetchone())
    from aos_api.aip_action_store import AipActionStore
    action = AipActionStore(head_action_connection).action_type_snapshot(
        TenantScope("org-org", "dev-project"), "ecommerce_growth_cutover")
    if action["id"] != "ecommerce_growth_cutover":
        raise ValueError("W5C3PR_CUTOVER_ACTION_UNAVAILABLE")
    return {"outcome": "W5C3PR_READ_ONLY_PRIVILEGES", "runtimeRole": role,
            "headConnection": head, "appConnection": app,
            "scopedHeadConnection": scoped,
            "cutoverActionRevisionHash": action["revisionHash"], "tables": rows}


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False))
