"""Independent withdrawal coordination; fixtures own disposable PostgreSQL."""
from tests.aip.test_provider_capacity_request_pg import original_inputs, SCOPE


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
