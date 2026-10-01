"""Isolated PostgreSQL proof for the first Model Eval budget hold schema."""

import psycopg

from aos_api.db import get_dsn


def test_model_eval_hold_schema_is_tenant_scoped_and_append_only():
    with psycopg.connect(get_dsn()) as conn:
        rows = conn.execute("""
            SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
                   has_table_privilege('aos_runtime',c.oid,'SELECT') AS can_read,
                   has_table_privilege('aos_runtime',c.oid,'INSERT') AS can_insert,
                   has_table_privilege('aos_runtime',c.oid,'UPDATE') AS can_update,
                   has_table_privilege('aos_runtime',c.oid,'DELETE') AS can_delete
              FROM pg_class c
             WHERE c.relnamespace='public'::regnamespace
               AND c.relname IN ('aip_model_eval_budget_reservation',
                                 'aip_model_eval_budget_reservation_bucket')
             ORDER BY c.relname
        """).fetchall()
        assert len(rows) == 2
        for row in rows:
            assert row[1:3] == (True, True)
            assert row[3:7] == (True, True, False, False)
        guards = conn.execute("""
            SELECT tgrelid::regclass::text,tgname FROM pg_trigger
             WHERE tgrelid IN ('aip_model_eval_budget_reservation'::regclass,
                               'aip_model_eval_budget_reservation_bucket'::regclass)
               AND NOT tgisinternal
        """).fetchall()
        for table in ('aip_model_eval_budget_reservation',
                      'aip_model_eval_budget_reservation_bucket'):
            assert any(name.startswith('trg_') and 'append_only' in name
                       for rel, name in guards if rel == table)
