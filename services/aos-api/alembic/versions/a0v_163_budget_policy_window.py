"""Closed initial policy subwindow authority; runtime bridge remains separate.

Reuses existing purpose roles without changing LOGIN or provisioning identity.
An isolated native acceptance and reviewed complete adapter are required before
deployment. This migration is not business approval or a Provider start grant.
"""
import json
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = 'a0v_163'
down_revision = 'a0v_162'
branch_labels = depends_on = None

M_CALL = 'aos_budget_renewal_maker_call'
I_CALL = 'aos_budget_renewal_issuer_call'
C_CALL = 'aos_budget_consumer_call'
M_OWNER = 'aos_budget_renewal_proposal_owner'
I_OWNER = 'aos_budget_renewal_issuer_owner'
C_OWNER = 'aos_budget_consumer_owner'
OWNERS = (M_OWNER, I_OWNER, C_OWNER)
TABLES = tuple('aip_budget_policy_window_' + name for name in
               ('proposal', 'decision', 'receipt', 'binding', 'fence'))
PARENT_FACTS = ('aip_budget_cost_proposal', 'aip_budget_cost_decision',
                'aip_budget_cost_revocation', 'aip_budget_receipt', 'aip_budget_cost_runtime_fence')
ORIGINAL = PARENT_FACTS + ('aip_budget_head', 'aip_budget_revision',
    'aip_provider_instance_head', 'aip_provider_instance_revision', 'meta_membership',
    'aip_model_governance_policy_head', 'aip_model_governance_policy_revision',
    'aip_model_price_snapshot_head', 'aip_model_price_snapshot_revision')
FUNCTIONS = {
    'command(jsonb,text)': (C_OWNER, False),
    'relation_shape(oid)': (C_OWNER, False),
    'profile(text)': (C_OWNER, False),
    'parent(jsonb,boolean)': (C_OWNER, False),
    'expected(jsonb,text)': (C_OWNER, False),
    'history(jsonb,text,text)': (C_OWNER, False),
    'proposal_fact(text,text,boolean)': (C_OWNER, False),
    'propose(jsonb)': (M_OWNER, True),
    'decide(jsonb,text)': (I_OWNER, True),
    'revoke(jsonb,text)': (I_OWNER, True),
    'consume(jsonb)': (C_OWNER, True),
    'reconcile(jsonb,text,text)': (C_OWNER, True),
    'guard_journal()': (C_OWNER, False),
    'guard_fence()': (C_OWNER, False),
    'complete_consume()': (C_OWNER, True),
}
REUSED = (
    'public.aip_budget_cost_hash_a0v_126(jsonb)',
    'public.canonical_asset_registry_jsonb(jsonb)',
    'public.guard_aip4_append_only()',
    'public.aip_budget_consumption_fact_a0v_128(text,text,text,text,text,text)',
    'public.aip_budget_cost_actor_a0v_127(text,text,text,text,text)',
    'public.aip_cost_configuration_write_guard_a0v_128()',
    'public.aip_renewal_profile_a0v_162(text)',
)
SCOPE = """org_id='org-org' AND project_id='dev-project'
 AND org_id=NULLIF(current_setting('aos.org_id',true),'')
 AND project_id=NULLIF(current_setting('aos.project_id',true),'')"""


def signature(short):
    name, args = short.split('(', 1)
    return f'public.aip_policy_window_{name}_v1({args}'


def function_shape(conn, name):
    return conn.execute(text("""SELECT jsonb_build_object('signature',CAST(:signature AS text),
      'owner',pg_get_userbyid(p.proowner),'definer',p.prosecdef,'config',to_jsonb(p.proconfig),
      'acl',p.proacl::text,'bodySha256',encode(public.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex'))
      FROM pg_proc p WHERE p.oid=to_regprocedure(:signature)"""), {'signature': name}).scalar_one()


def original_seal(conn):
    value = conn.execute(text("SELECT obj_description('public.aip_budget_policy_renewal_proposal'::regclass,'pg_class')")).scalar_one()
    value = json.loads(value) if isinstance(value, str) else value
    if (not isinstance(value, dict) or value.get('schema') != 'aos-renewal-schema-seal/v1'
            or len(value.get('functions', [])) != 22 or len(value.get('relations', [])) != 10):
        raise RuntimeError('POLICY_WINDOW_ORIGINAL_162_SEAL_REQUIRED')
    for item in value['functions']:
        if function_shape(conn, item['signature']) != item:
            raise RuntimeError('POLICY_WINDOW_ORIGINAL_FUNCTION_DRIFT')
    for item in value['relations']:
        actual = conn.execute(text('SELECT public.aip_renewal_relation_shape_a0v_162(to_regclass(:name))'),
                              {'name': 'public.' + item['name']}).scalar_one()
        if actual != item:
            raise RuntimeError('POLICY_WINDOW_ORIGINAL_RELATION_DRIFT')
    return value


def upgrade():
    conn = op.get_bind()
    before = original_seal(conn)
    if conn.execute(text("""SELECT EXISTS(SELECT 1 FROM public.aip_model_governance_policy_head
       WHERE policy_id LIKE 'window-policy-%') OR EXISTS(
       SELECT 1 FROM public.aip_model_price_snapshot_head WHERE model_price_snapshot_id LIKE 'window-price-%')""")).scalar_one():
        raise RuntimeError('POLICY_WINDOW_RESERVED_NAMESPACE_RECONCILIATION_REQUIRED')
    # Role collisions are not repaired, no passwords or LOGIN state are changed.
    for owner in OWNERS:
        row = conn.execute(text("""SELECT rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls
          OR rolcreatedb OR rolcreaterole OR rolreplication OR EXISTS(
           SELECT 1 FROM pg_auth_members WHERE roleid=pg_roles.oid OR member=pg_roles.oid)
          FROM pg_roles WHERE rolname=:name"""), {'name': owner}).scalar_one()
        if row:
            raise RuntimeError('POLICY_WINDOW_OWNER_PROFILE_DRIFT')
    for table in ORIGINAL:
        if not conn.execute(text('SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid=to_regclass(:name)'),
                            {'name': 'public.' + table}).scalar_one():
            raise RuntimeError('POLICY_WINDOW_FORCE_RLS_REQUIRED')
    source = Path(__file__).resolve().parents[2] / 'aos_api/aip_budget_policy_window_authority.sql'
    conn.exec_driver_sql(source.read_text().replace('%', '%%'))
    for table in TABLES:
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        # Clear even inherited installer default ACLs before installing the exact map.
        grantees = conn.execute(text("""SELECT DISTINCT r.rolname FROM pg_class c,
          LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a JOIN pg_roles r ON r.oid=a.grantee
          WHERE c.oid=to_regclass(:name) AND a.grantee<>c.relowner"""), {'name': 'public.' + table}).scalars().all()
        for grantee in grantees:
            op.execute(f'REVOKE ALL ON public.{table} FROM {conn.dialect.identifier_preparer.quote(grantee)}')
        op.execute(f'REVOKE ALL ON public.{table} FROM PUBLIC')
        for owner in OWNERS:
            op.execute(f'GRANT SELECT ON public.{table} TO {owner}')
        op.execute(f'CREATE POLICY policy_window_scope_v1 ON public.{table} TO {",".join(OWNERS)} '
                   f'USING({SCOPE}) WITH CHECK({SCOPE})')
        if table != TABLES[-1]:
            op.execute(f'CREATE TRIGGER policy_window_append_only BEFORE UPDATE OR DELETE ON public.{table} '
                       'FOR EACH ROW EXECUTE FUNCTION public.guard_aip4_append_only()')
            op.execute(f'CREATE TRIGGER policy_window_insert_guard BEFORE INSERT ON public.{table} '
                       'FOR EACH ROW EXECUTE FUNCTION public.aip_policy_window_guard_journal_v1()')
        op.execute(f'CREATE TRIGGER policy_window_truncate_guard BEFORE TRUNCATE ON public.{table} '
                   'FOR EACH STATEMENT EXECUTE FUNCTION public.guard_aip4_append_only()')
    for table in PARENT_FACTS:
        op.execute(f'GRANT SELECT ON public.{table} TO {M_OWNER},{I_OWNER}')
        op.execute(f'CREATE POLICY policy_window_parent_read_v1 ON public.{table} TO {M_OWNER},{I_OWNER} '
                   f'USING({SCOPE})')
    op.execute(f'GRANT INSERT ON public.{TABLES[0]},{TABLES[4]} TO {M_OWNER}')
    op.execute(f'GRANT INSERT ON public.{TABLES[1]} TO {I_OWNER}')
    op.execute(f'GRANT INSERT ON public.{TABLES[3]} TO {C_OWNER}')
    op.execute(f'GRANT INSERT ON public.{TABLES[2]} TO {",".join(OWNERS)}')
    op.execute(f'GRANT UPDATE(version,revoked,modified_at) ON public.{TABLES[4]} TO {I_OWNER}')
    op.execute(f'GRANT UPDATE(version,modified_at) ON public.{TABLES[4]} TO {C_OWNER}')
    op.execute(f'CREATE TRIGGER policy_window_fence_guard BEFORE INSERT OR UPDATE OR DELETE ON public.{TABLES[4]} '
               'FOR EACH ROW EXECUTE FUNCTION public.aip_policy_window_guard_fence_v1()')
    for short, (owner, _) in FUNCTIONS.items():
        name = signature(short)
        op.execute(f'ALTER FUNCTION {name} OWNER TO {owner}')
        grantees = conn.execute(text("""SELECT DISTINCT r.rolname FROM pg_proc p,
          LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a JOIN pg_roles r ON r.oid=a.grantee
          WHERE p.oid=to_regprocedure(:name) AND a.grantee<>p.proowner"""), {'name': name}).scalars().all()
        for grantee in grantees:
            op.execute(f'REVOKE ALL ON FUNCTION {name} FROM {conn.dialect.identifier_preparer.quote(grantee)}')
        op.execute(f'REVOKE ALL ON FUNCTION {name} FROM PUBLIC')
        for reader in OWNERS:
            op.execute(f'GRANT EXECUTE ON FUNCTION {name} TO {reader}')
    for short, caller in (('propose(jsonb)', M_CALL), ('decide(jsonb,text)', I_CALL),
                          ('revoke(jsonb,text)', I_CALL), ('consume(jsonb)', C_CALL)):
        op.execute(f'GRANT EXECUTE ON FUNCTION {signature(short)} TO {caller}')
    op.execute(f'GRANT EXECUTE ON FUNCTION {signature("reconcile(jsonb,text,text)")} TO {M_CALL},{I_CALL},{C_CALL}')
    # Completeness attaches to outputs too: omitting Receipt entirely must fail,
    # and old policy-only renewal cannot publish a new-family successor alone.
    for table in (TABLES[2], TABLES[3], 'aip_model_price_snapshot_revision', 'aip_model_governance_policy_revision'):
        op.execute(f'CREATE CONSTRAINT TRIGGER policy_window_complete_v1 AFTER INSERT ON public.{table} '
                   'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW '
                   'EXECUTE FUNCTION public.aip_policy_window_complete_consume_v1()')
    if original_seal(conn) != before:
        raise RuntimeError('POLICY_WINDOW_ORIGINAL_SEAL_CHANGED')
    seal = {'schema': 'aos-policy-window-native-seal/v1',
            'functions': [function_shape(conn, name) for name in [*map(signature, FUNCTIONS), *REUSED]],
            'relations': [conn.execute(text('SELECT public.aip_policy_window_relation_shape_v1(to_regclass(:name))'),
                                      {'name': 'public.' + name}).scalar_one() for name in (*TABLES, *ORIGINAL)]}
    if len(seal['functions']) != 22 or len(seal['relations']) != 19:
        raise RuntimeError('POLICY_WINDOW_NATIVE_MANIFEST_COUNT')
    encoded = json.dumps(seal, ensure_ascii=False, sort_keys=True).replace("'", "''")
    op.execute("COMMENT ON TABLE public.aip_budget_policy_window_proposal IS '" + encoded + "'")


def downgrade():
    raise RuntimeError('POLICY_WINDOW_IMMUTABLE_HISTORY_REQUIRES_FORWARD_RECOVERY')
