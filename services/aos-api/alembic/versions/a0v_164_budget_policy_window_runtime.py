"""Add a closed child provenance entry without changing old sealed relations.

The caller must still prove the original parent and hold its current head locks.
This migration does not provision a login, configure runtime admission, or start
a Provider. Its independent seal must be pinned outside the database before use.
"""
import hashlib
import json
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = 'a0v_164'
down_revision = 'a0v_163'
branch_labels = depends_on = None

ENTRY = 'public.aip_policy_window_risk_fact_v1(jsonb,jsonb)'
OWNER = 'aos_budget_consumer_owner'
CALLERS = ('aos_runtime', 'aos_aip_binding_evaluator')


def function_shape(conn, signature):
    return conn.execute(text("""SELECT jsonb_build_object('signature',CAST(:signature AS text),
      'owner',pg_get_userbyid(p.proowner),'definer',p.prosecdef,'config',to_jsonb(p.proconfig),
      'acl',p.proacl::text,'bodySha256',encode(public.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex'))
      FROM pg_catalog.pg_proc p WHERE p.oid=pg_catalog.to_regprocedure(:signature)"""),
      {'signature': signature}).scalar_one()


def original_seals(conn):
    """Compare all original function/relationship records; never rewrite a seal."""
    found = {}
    for table, schema, count in (
            ('aip_budget_policy_renewal_proposal', 'aos-renewal-schema-seal/v1', 10),
            ('aip_budget_policy_window_proposal', 'aos-policy-window-native-seal/v1', 19)):
        raw = conn.execute(text('SELECT pg_catalog.obj_description(pg_catalog.to_regclass(:name),:kind)'),
                           {'name': 'public.' + table, 'kind': 'pg_class'}).scalar_one()
        seal = json.loads(raw) if isinstance(raw, str) else None
        if (not isinstance(seal, dict) or set(seal) != {'schema', 'functions', 'relations'}
                or seal['schema'] != schema or len(seal['functions']) != 22
                or len(seal['relations']) != count):
            raise RuntimeError('POLICY_WINDOW_RUNTIME_ORIGINAL_SEAL_REQUIRED')
        for item in seal['functions']:
            if function_shape(conn, item['signature']) != item:
                raise RuntimeError('POLICY_WINDOW_RUNTIME_ORIGINAL_FUNCTION_DRIFT')
        for item in seal['relations']:
            actual = conn.execute(text('SELECT public.aip_policy_window_relation_shape_v1('
                'pg_catalog.to_regclass(:name))'), {'name': 'public.' + item['name']}).scalar_one()
            # The old 162 seal intentionally predates trigger/index metadata.
            if not isinstance(actual, dict) or {key: actual[key] for key in item} != item:
                raise RuntimeError('POLICY_WINDOW_RUNTIME_ORIGINAL_RELATION_DRIFT')
        found[table] = hashlib.sha256(raw.encode()).hexdigest()
    return found


def upgrade():
    conn = op.get_bind()
    before = original_seals(conn)
    if conn.execute(text('SELECT pg_catalog.to_regprocedure(:name) IS NOT NULL'),
                    {'name': ENTRY}).scalar_one():
        raise RuntimeError('POLICY_WINDOW_RUNTIME_ENTRY_COLLISION_RECONCILE_REQUIRED')
    closed = conn.execute(text("""SELECT NOT(rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls
        OR rolcreatedb OR rolcreaterole OR rolreplication) AND NOT EXISTS(
          SELECT 1 FROM pg_catalog.pg_auth_members WHERE roleid=r.oid OR member=r.oid)
        FROM pg_catalog.pg_roles r WHERE rolname=:owner"""), {'owner': OWNER}).scalar_one()
    if not closed:
        raise RuntimeError('POLICY_WINDOW_RUNTIME_CLOSED_OWNER_REQUIRED')
    # No old functions, policies, role membership, privileges or tables change.
    source = Path(__file__).resolve().parents[2] / 'aos_api/aip_budget_policy_window_runtime_authority.sql'
    conn.exec_driver_sql(source.read_text().replace('%', '%%'))
    op.execute(f'ALTER FUNCTION {ENTRY} OWNER TO {OWNER}')
    grantees = conn.execute(text("""SELECT DISTINCT r.rolname FROM pg_catalog.pg_proc p,
        LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
        WHERE p.oid=pg_catalog.to_regprocedure(:name) AND a.grantee<>p.proowner"""),
        {'name': ENTRY}).scalars().all()
    for role in grantees:
        op.execute(f'REVOKE ALL ON FUNCTION {ENTRY} FROM {conn.dialect.identifier_preparer.quote(role)}')
    op.execute(f'REVOKE ALL ON FUNCTION {ENTRY} FROM PUBLIC')
    for caller in CALLERS:
        op.execute(f'GRANT EXECUTE ON FUNCTION {ENTRY} TO {caller}')
    if original_seals(conn) != before:
        raise RuntimeError('POLICY_WINDOW_RUNTIME_ORIGINAL_SEAL_CHANGED')
    seal = dict(schema='aos-policy-window-runtime-seal/v1', function=function_shape(conn, ENTRY),
                dependencies=before, runtimeLogin='aos_a0v_runtime_20260912',
                runtimeRole='aos_runtime', evaluatorLogin='aos_aip_binding_evaluator')
    encoded = json.dumps(seal, ensure_ascii=False, sort_keys=True).replace("'", "''")
    op.execute(f"COMMENT ON FUNCTION {ENTRY} IS '{encoded}'")


def downgrade():
    raise RuntimeError('POLICY_WINDOW_RUNTIME_REQUIRES_FORWARD_RECOVERY')
