"""The old unknown transition must not remain a runtime-callable bypass."""

import os

import psycopg
import pytest


OLD_RECONCILE = (
    "public.data_requirement_outbox_reconcile_completed_a0v_050"
    "(text,bigint,text,jsonb,jsonb)"
)
NORMAL_COMPLETE = (
    "public.data_requirement_outbox_complete_a0v_050"
    "(text,bigint,text,jsonb,jsonb)"
)


def test_legacy_unknown_reconcile_runtime_execute_is_revoked_in_disposable_pg():
    dsn = os.environ["AOS_DATABASE_URL"]
    with psycopg.connect(dsn, autocommit=True) as conn:
        assert conn.info.dbname.startswith("aos_test_")
        before = conn.execute(
            "SELECT count(*) FROM public.data_requirement_outbox_delivery"
        ).fetchone()[0]
        old_allowed, normal_allowed = conn.execute(
            "SELECT has_function_privilege('aos_runtime',%s,'EXECUTE'),"
            "has_function_privilege('aos_runtime',%s,'EXECUTE')",
            (OLD_RECONCILE, NORMAL_COMPLETE),
        ).fetchone()
        assert old_allowed is False
        assert normal_allowed is True
        for role in ("aos_extension_directory", "aos_extension_maintainer"):
            assert conn.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE')",
                (role, OLD_RECONCILE),
            ).fetchone()[0] is False

        conn.execute("SET ROLE aos_runtime")
        conn.execute(
            "SELECT set_config('aos.org_id','org-org',false),"
            "set_config('aos.project_id','dev-project',false)"
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT * FROM public.data_requirement_outbox_reconcile_completed_a0v_050"
                "(%s,%s,%s,%s::jsonb,%s::jsonb)",
                ("missing-original", 1, "original-token", "{}", "{}"),
            )
        conn.execute("RESET ROLE")
        after = conn.execute(
            "SELECT count(*) FROM public.data_requirement_outbox_delivery"
        ).fetchone()[0]
        assert after == before
