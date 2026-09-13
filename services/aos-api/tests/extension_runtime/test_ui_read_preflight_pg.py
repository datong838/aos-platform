import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest

from aos_api.extension_runtime.ui_read_preflight import runtime_ui_read_ready


@pytest.fixture
def full_ui_database():
    # The autouse fixture already migrated a private disposable database to head.
    parts=conninfo_to_dict(os.environ['AOS_DATABASE_URL'])
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    login='ui_probe_'+uuid4().hex
    with psycopg.connect(**parts,autocommit=True) as owner:
        owner.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(login)))
        owner.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(login)))
        try:
            with psycopg.connect(**(parts|{'user':login}),autocommit=True) as reader:
                yield owner,reader
        finally:owner.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(login)))


def test_full_migrated_schema_passes_non_superuser_read_only_preflight(full_ui_database):
    _,reader=full_ui_database
    ready=runtime_ui_read_ready(reader)
    diagnostic=reader.execute("""SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
        pg_has_role(session_user,c.relowner,'MEMBER'),c.relacl::text
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname=ANY(%s) ORDER BY c.relname""",
        (['extension_runtime_ui_read_request','extension_runtime_execution_attempt','extension_runtime_binding',
          'ecommerce_investigation_case_head','ecommerce_investigation_case_revision','ecommerce_investigation_run',
          'ecommerce_investigation_run_state_head'],)).fetchall()
    assert ready is True, diagnostic


@pytest.mark.parametrize('change,restore',[
    ('ALTER TABLE public.ecommerce_investigation_case_head NO FORCE ROW LEVEL SECURITY',
     'ALTER TABLE public.ecommerce_investigation_case_head FORCE ROW LEVEL SECURITY'),
    ('GRANT INSERT ON public.extension_runtime_ui_read_request TO aos_runtime',
     'REVOKE INSERT ON public.extension_runtime_ui_read_request FROM aos_runtime'),
    ('GRANT UPDATE(subject) ON public.extension_runtime_ui_read_request TO aos_runtime',
     'REVOKE UPDATE(subject) ON public.extension_runtime_ui_read_request FROM aos_runtime'),
    ('GRANT EXECUTE ON FUNCTION public.extension_ui_read_host_principal_a0v_033(text,text[]) TO aos_ui_read_api',
     'REVOKE EXECUTE ON FUNCTION public.extension_ui_read_host_principal_a0v_033(text,text[]) FROM aos_ui_read_api'),
    ('REVOKE UPDATE(result_hash) ON public.extension_runtime_ui_read_request FROM aos_runtime',
     'GRANT UPDATE(result_hash) ON public.extension_runtime_ui_read_request TO aos_runtime'),
])
def test_preflight_rejects_missing_or_expanded_rights(full_ui_database,change,restore):
    owner,reader=full_ui_database
    owner.execute(change)
    try:assert runtime_ui_read_ready(reader) is False
    finally:owner.execute(restore)
    assert runtime_ui_read_ready(reader) is True
