"""Isolated protocol probe; not an installed issuer or a production migration."""
import psycopg
import pytest
from psycopg import sql

from test_lifecycle_pg import database, pytestmark
from current_configuration_sources_case import source_case


def test_database_writer_trigger_waits_for_select_only_plan_reader(source_case, database):
    conn, _ = source_case
    _, role, schema = database
    conn.execute('RESET ROLE')
    conn.execute('''CREATE FUNCTION test_plan_version_lock() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            PERFORM pg_advisory_xact_lock(hashtextextended(
                'aos-plan:' || jsonb_build_array(NEW.org_id,NEW.project_id,NEW.plan_id)::text, 0));
            RETURN NEW;
        END $$''')
    conn.execute('''CREATE TRIGGER test_plan_version_lock BEFORE UPDATE
        ON aip_responsibility_plan_head FOR EACH ROW
        EXECUTE FUNCTION test_plan_version_lock()''')
    conn.execute('REVOKE UPDATE ON aip_responsibility_plan_head FROM aos_runtime')
    conn.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(role)))
    conn.execute('SET ROLE aos_runtime')
    with psycopg.connect(host='127.0.0.1', port=18432, user='postgres',
                         dbname='postgres', autocommit=True) as writer:
        writer.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        writer.execute("SET statement_timeout='250ms'")
        with conn.transaction():
            conn.execute('''SELECT pg_advisory_xact_lock(hashtextextended(
                'aos-plan:' || jsonb_build_array(%s::text,%s::text,%s::text)::text, 0))''',
                ('org-org', 'dev-project', 'qyh-runtime-roles'))
            assert conn.execute('''SELECT current_revision FROM aip_responsibility_plan_head
                WHERE org_id=%s AND project_id=%s AND plan_id=%s''',
                ('org-org', 'dev-project', 'qyh-runtime-roles')).fetchone()[0] == 1
            with pytest.raises(psycopg.errors.QueryCanceled):
                writer.execute('''UPDATE aip_responsibility_plan_head
                    SET version=version+1 WHERE org_id=%s AND project_id=%s AND plan_id=%s''',
                    ('org-org', 'dev-project', 'qyh-runtime-roles'))
        writer.execute('''UPDATE aip_responsibility_plan_head SET version=version+1
            WHERE org_id=%s AND project_id=%s AND plan_id=%s''',
            ('org-org', 'dev-project', 'qyh-runtime-roles'))
    conn.execute('RESET SESSION AUTHORIZATION')
    assert conn.execute('SELECT version FROM aip_responsibility_plan_head').fetchone()[0] == 2
