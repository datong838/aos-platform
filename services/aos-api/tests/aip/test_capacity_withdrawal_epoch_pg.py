"""Independent withdrawal coordination; fixtures own disposable PostgreSQL."""
from tests.aip.test_provider_capacity_request_pg import original_inputs, SCOPE
from tests.aip.test_provider_capacity_action_pg import drafted


def test_withdrawal_epoch_is_private_and_backfilled(original_inputs):
    from tests.aip.test_provider_capacity_formal_boundary_pg import isolated_owner
    with isolated_owner() as conn:
        row=conn.execute("SELECT relowner='aos_capacity_withdrawal_epoch_owner'::regrole AS owner,relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.aip_capacity_withdrawal_epoch'::regclass").fetchone()
        assert row == dict(owner=True,relrowsecurity=True,relforcerowsecurity=True)
        assert conn.execute("SELECT count(*) AS n FROM public.aip_action_proposal p WHERE p.org_id='org-org' AND p.project_id='dev-project' AND NOT EXISTS(SELECT 1 FROM public.aip_capacity_withdrawal_epoch e WHERE (e.org_id,e.project_id,e.proposal_id)=(p.org_id,p.project_id,p.proposal_id))").fetchone()['n']==0
        assert not conn.execute("SELECT 1 FROM pg_proc p,LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.proname LIKE 'aos_capacity_withdrawal_epoch_%' AND a.grantee=0").fetchone()


import pytest


@pytest.mark.parametrize('fault', ['table_acl','policy','function_acl','function_mode','trigger','foreign_key','owner_schema','owner_extra','column','constraint'])
def test_withdrawal_boundary_rejects_actual_catalog_drift(original_inputs, fault):
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence, CapacityWithdrawalFenceBlocked
    from tests.aip.test_provider_capacity_formal_boundary_pg import isolated_owner
    from psycopg import sql
    with isolated_owner() as conn:
        require_withdrawal_fence(conn)
        changes={
            'table_acl': 'GRANT SELECT ON public.aip_capacity_withdrawal_epoch TO aos_runtime',
            'policy': 'ALTER POLICY capacity_withdrawal_epoch_scope ON public.aip_capacity_withdrawal_epoch USING(true)',
            'function_acl': 'GRANT EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) TO PUBLIC',
            'function_mode': 'ALTER FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) SECURITY INVOKER',
            'trigger': 'ALTER TABLE public.aip_action_withdrawal_event DISABLE TRIGGER zz_capacity_withdrawal_epoch_bump_a0v151',
            'owner_schema': 'GRANT CREATE ON SCHEMA public TO aos_capacity_withdrawal_epoch_owner',
            'owner_extra': 'GRANT SELECT ON public.meta_action_type TO aos_capacity_withdrawal_epoch_owner',
            'column': 'ALTER TABLE public.aip_capacity_withdrawal_epoch ALTER COLUMN epoch DROP NOT NULL',
            'constraint': 'ALTER TABLE public.aip_capacity_withdrawal_epoch DROP CONSTRAINT aip_capacity_withdrawal_epoch_epoch_check',
        }
        conn.execute('SAVEPOINT drift')
        if fault=='foreign_key':
            name=conn.execute("SELECT conname FROM pg_constraint WHERE conrelid='public.aip_action_withdrawal_event'::regclass AND contype='f'").fetchone()['conname']
            conn.execute(sql.SQL('ALTER TABLE public.aip_action_withdrawal_event ALTER CONSTRAINT {} DEFERRABLE INITIALLY DEFERRED').format(sql.Identifier(name)))
        else: conn.execute(changes[fault])
        try:
            with pytest.raises(CapacityWithdrawalFenceBlocked): require_withdrawal_fence(conn)
        finally:
            conn.execute('ROLLBACK TO SAVEPOINT drift')
        require_withdrawal_fence(conn)


@pytest.mark.parametrize("migration_fault", ['none', 'deferred-fk', 'duplicate-function'])
@pytest.mark.parametrize("full_alembic", [False, True], ids=['migration-function', 'alembic-version-transaction'])
def test_nonempty_historical_withdrawal_backfill_preserves_original_rows(drafted, migration_fault, full_alembic):
    """Reconstructed nonempty history; not a full historical backup restore."""
    import importlib.util
    import os
    from pathlib import Path
    from uuid import uuid4
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.exc import DBAPIError

    assert '/aos_test_' in os.environ['AOS_DATABASE_URL']
    engine = create_engine(os.environ['AOS_DATABASE_URL'].replace('postgresql://', 'postgresql+psycopg://', 1))
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_151_capacity_withdrawal_epoch.py'
    spec = importlib.util.spec_from_file_location('withdrawal151_drill', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.exec_driver_sql("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
                proposal = conn.exec_driver_sql("SELECT * FROM public.aip_action_proposal WHERE org_id='org-org' AND project_id='dev-project' LIMIT 1").mappings().first()
                assert proposal is not None, 'nonempty original proposal history required'
                conn.exec_driver_sql('DROP TRIGGER zz_capacity_withdrawal_epoch_init_a0v151 ON public.aip_action_proposal')
                conn.exec_driver_sql('DROP TRIGGER zz_capacity_withdrawal_epoch_bump_a0v151 ON public.aip_action_withdrawal_event')
                for name, args in [('lock','text,text,text'),('init',''),('bump','')]:
                    conn.exec_driver_sql(f'DROP FUNCTION public.aos_capacity_withdrawal_epoch_{name}({args})')
                conn.exec_driver_sql('DROP TABLE public.aip_capacity_withdrawal_epoch')
                conn.exec_driver_sql('REVOKE USAGE ON SCHEMA public FROM aos_capacity_withdrawal_epoch_owner')
                if full_alembic:
                    # Only the disposable fixture's outer rollback transaction
                    # may reconstruct the predecessor; no production downgrade.
                    conn.exec_driver_sql("UPDATE alembic_version SET version_num='a0v_150' WHERE version_num='a0v_151'")
                expected_before = 'a0v_150' if full_alembic else 'a0v_151'
                assert conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == expected_before

                def upgrade():
                    if full_alembic:
                        config = Config()
                        config.set_main_option('script_location', str(path.parent.parent))
                        config.attributes['connection'] = conn
                        command.upgrade(config, 'a0v_151')
                    else:
                        with Operations.context(MigrationContext.configure(conn)):
                            migration.upgrade()
                conn.exec_driver_sql("INSERT INTO public.aip_action_withdrawal_event (org_id,project_id,withdrawal_event_id,proposal_id,proposal_version,proposal_hash,actor_id,reason,idempotency_key,request_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    ('org-org','dev-project','history-'+uuid4().hex,proposal['proposal_id'],proposal['version']+1,proposal['proposal_hash'],proposal['created_by'],'isolated historical migration drill','history-key-'+uuid4().hex,'f'*64))
                queries = [f'SELECT row_to_json(t)::text FROM public.{table} t ORDER BY row_to_json(t)::text' for table in ('aip_action_proposal','aip_action_withdrawal_event')]
                before = [conn.exec_driver_sql(q).all() for q in queries]
                schema_acl_before = conn.exec_driver_sql("SELECT nspacl::text FROM pg_namespace WHERE nspname='public'").scalar_one()
                if migration_fault != 'none':
                    # Roll back the rejected attempt, including its precondition drift.
                    savepoint = conn.begin_nested()
                    if migration_fault == 'deferred-fk':
                        fk = conn.exec_driver_sql("SELECT conname FROM pg_constraint WHERE conrelid='public.aip_action_withdrawal_event'::regclass AND contype='f' ORDER BY conname LIMIT 1").scalar_one()
                        quoted = conn.dialect.identifier_preparer.quote(fk)
                        conn.exec_driver_sql(f'ALTER TABLE public.aip_action_withdrawal_event ALTER CONSTRAINT {quoted} DEFERRABLE INITIALLY DEFERRED')
                        expected_error = 'CAPACITY_WITHDRAWAL_FOREIGN_KEY_ORDER_REQUIRED'
                    else:
                        # Real failure after table/backfill/RLS/ownership DDL.
                        conn.exec_driver_sql("CREATE FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) RETURNS bigint LANGUAGE sql AS 'SELECT 0::bigint'")
                        expected_error = 'already exists with same argument types'
                    with pytest.raises(DBAPIError, match=expected_error):
                        upgrade()
                    savepoint.rollback()
                    assert conn.exec_driver_sql("SELECT to_regclass('public.aip_capacity_withdrawal_epoch')").scalar_one() is None
                    for name, args in [('lock', 'text,text,text'), ('init', ''), ('bump', '')]:
                        assert conn.exec_driver_sql('SELECT to_regprocedure(%s)', (f'public.aos_capacity_withdrawal_epoch_{name}({args})',)).scalar_one() is None
                    assert conn.exec_driver_sql("SELECT count(*) FROM pg_trigger WHERE tgname IN ('zz_capacity_withdrawal_epoch_init_a0v151','zz_capacity_withdrawal_epoch_bump_a0v151')").scalar_one() == 0
                    assert conn.exec_driver_sql("SELECT nspacl::text FROM pg_namespace WHERE nspname='public'").scalar_one() == schema_acl_before
                    assert conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == expected_before
                    assert [conn.exec_driver_sql(q).all() for q in queries] == before
                upgrade()
                assert conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == 'a0v_151'
                assert [conn.exec_driver_sql(q).all() for q in queries] == before
                assert conn.exec_driver_sql("SELECT count(*) FROM public.aip_action_proposal p FULL JOIN public.aip_capacity_withdrawal_epoch e USING(org_id,project_id,proposal_id) WHERE coalesce(p.org_id,e.org_id)='org-org' AND coalesce(p.project_id,e.project_id)='dev-project' AND (p.proposal_id IS NULL OR e.proposal_id IS NULL OR e.epoch<>(SELECT count(*) FROM public.aip_action_withdrawal_event w WHERE (w.org_id,w.project_id,w.proposal_id)=(p.org_id,p.project_id,p.proposal_id)))").scalar_one() == 0
                assert conn.exec_driver_sql('SELECT count(*) FROM public.aip_capacity_withdrawal_epoch WHERE epoch>0').scalar_one() > 0
                rejected = conn.begin_nested()
                with pytest.raises(DBAPIError, match='CAPACITY_APPROVAL_WITHDRAWN'):
                    conn.exec_driver_sql('SELECT public.aos_capacity_withdrawal_epoch_lock(%s,%s,%s)', ('org-org','dev-project',proposal['proposal_id']))
                rejected.rollback()
            finally:
                transaction.rollback()
            assert conn.exec_driver_sql("SELECT to_regclass('public.aip_capacity_withdrawal_epoch') IS NOT NULL").scalar_one()
            assert conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == 'a0v_151'
    finally:
        engine.dispose()
