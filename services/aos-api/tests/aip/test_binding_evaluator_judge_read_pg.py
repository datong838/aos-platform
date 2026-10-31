"""Actual evaluator column boundary; empty counts do not prove hold admission."""
import pytest
import psycopg
import importlib.util
from pathlib import Path

from aos_api.aip_budget_cost_runtime import shared_risk_totals
from tests.aip.test_budget_policy_window_runtime_pg import (
    _isolated_postgres_database, actual_evaluator,
)
from tests.aip.test_budget_policy_window_native_pg import SCOPE

TABLE = 'public.aip_model_judge_budget_reservation'
COLUMNS = {'org_id', 'project_id', 'upper_bound_minor', 'budget_revision_ref'}


def test_evaluator_judge_risk_column_contract(actual_evaluator):
    with actual_evaluator() as conn:
        rows = conn.execute("""SELECT attname,has_column_privilege(current_user,
            attrelid,attname,'SELECT') AS allowed FROM pg_attribute
            WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped""", (TABLE,)).fetchall()
        assert {row['attname'] for row in rows if row['allowed']} == COLUMNS
        assert all(not conn.execute('SELECT has_table_privilege(current_user,%s,%s) AS allowed',
                   (TABLE, privilege)).fetchone()['allowed']
                   for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'))
        assert not conn.execute("""SELECT has_table_privilege(current_user,
            'public.aip_model_judge_budget_reservation_bucket','SELECT') AS allowed""").fetchone()['allowed']
        count, risk = shared_risk_totals(conn, SCOPE, 'boundary-only-no-such-budget')
        assert (count, risk) == (0, 0)
        conn.execute('SELECT org_id,project_id,upper_bound_minor,budget_revision_ref FROM ' + TABLE).fetchall()
        policy = conn.execute("""SELECT polcmd,polroles=ARRAY[current_user::regrole::oid] AS exact_role,
            pg_get_expr(polqual,polrelid) AS predicate,polwithcheck IS NULL AS no_write_check
            FROM pg_policy WHERE polrelid=%s::regclass AND polname=%s""",
            (TABLE, 'evaluator_judge_risk_read_a0v165')).fetchone()
        assert policy and policy['polcmd'] == 'r' and policy['exact_role'] and policy['no_write_check']
        assert all(value in policy['predicate'] for value in
                   ('org-org', 'dev-project', 'aos.org_id', 'aos.project_id'))
        conn.rollback()


def test_evaluator_cannot_read_judge_request_details(actual_evaluator):
    with actual_evaluator() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT request_id,approval_ref FROM ' + TABLE).fetchall()
        conn.rollback()


@pytest.mark.parametrize('organization', ['', 'dev-org'])
def test_evaluator_judge_read_scope_is_closed(actual_evaluator, organization):
    with actual_evaluator() as conn:
        conn.execute("SELECT set_config('aos.org_id',%s,true)", (organization,))
        assert conn.execute('SELECT count(*) AS n FROM ' + TABLE).fetchone()['n'] == 0
        conn.rollback()


@pytest.mark.parametrize('drift', ['none', 'public_select', 'public_policy'])
def test_migration_preflight_rejects_public_authority_drift(drift):
    from sqlalchemy import create_engine, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from aos_api.db import get_dsn
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_165_evaluator_judge_risk_read.py'
    spec = importlib.util.spec_from_file_location('_judge_read_candidate_preflight', path)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    engine = create_engine(get_dsn().replace('postgresql://', 'postgresql+psycopg://'),
                           isolation_level='SERIALIZABLE')
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                assert conn.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one() == 'a0v_165'
                # Rehearse only the old privilege shape inside a rolled-back
                # transaction. Never rerun an installed Alembic revision.
                before = conn.execute(text('SELECT public.aip_policy_window_relation_shape_v1('
                    "'public.aip_model_judge_budget_reservation'::regclass)")).scalar_one()
                conn.exec_driver_sql('REVOKE SELECT (org_id,project_id,upper_bound_minor,budget_revision_ref) '
                    'ON public.aip_model_judge_budget_reservation FROM aos_aip_binding_evaluator')
                conn.exec_driver_sql('DROP POLICY evaluator_judge_risk_read_a0v165 '
                    'ON public.aip_model_judge_budget_reservation')
                if drift == 'public_select':
                    conn.exec_driver_sql('GRANT SELECT ON public.aip_model_judge_budget_reservation TO PUBLIC')
                elif drift == 'public_policy':
                    conn.exec_driver_sql('CREATE POLICY isolated_public_read_drift ON '
                        'public.aip_model_judge_budget_reservation FOR SELECT TO PUBLIC USING (true)')
                with Operations.context(MigrationContext.configure(conn)):
                    if drift == 'none':
                        candidate.upgrade()
                        after = conn.execute(text('SELECT public.aip_policy_window_relation_shape_v1('
                            "'public.aip_model_judge_budget_reservation'::regclass)")).scalar_one()
                        assert after == before
                    else:
                        with pytest.raises(RuntimeError, match='EVALUATOR_JUDGE_READ_BOUNDARY_DRIFT'):
                            candidate.upgrade()
                        assert not conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_policy WHERE "
                            "polrelid='public.aip_model_judge_budget_reservation'::regclass "
                            "AND polname='evaluator_judge_risk_read_a0v165')")).scalar_one()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
