"""Let formal evaluation count Judge exposure without granting hold authority."""
import importlib.util
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = 'a0v_165'
down_revision = 'a0v_164'
branch_labels = depends_on = None

EVALUATOR = 'aos_aip_binding_evaluator'
TABLE = 'aip_model_judge_budget_reservation'
COLUMNS = ('org_id', 'project_id', 'upper_bound_minor', 'budget_revision_ref')
POLICY = 'evaluator_judge_risk_read_a0v165'


def upgrade():
    conn = op.get_bind()
    # Use the existing verifier; never copy or rewrite old sealed authority.
    path = Path(__file__).with_name('a0v_164_budget_policy_window_runtime.py')
    spec = importlib.util.spec_from_file_location('_evaluator_judge_original_seals', path)
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    seals = previous.original_seals(conn)
    runtime = previous.function_shape(conn, previous.ENTRY)
    role = conn.execute(text("""SELECT NOT(rolcanlogin OR rolinherit OR rolsuper
        OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)
        AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members
          WHERE roleid=r.oid OR member=r.oid)
        FROM pg_catalog.pg_roles r WHERE rolname=:role"""), {'role': EVALUATOR}).scalar_one()
    table = conn.execute(text("""SELECT relrowsecurity AND relforcerowsecurity
        FROM pg_catalog.pg_class WHERE oid=pg_catalog.to_regclass(:name)"""),
        {'name': 'public.' + TABLE}).scalar_one()
    collision = conn.execute(text("""SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_policy
        WHERE polrelid=pg_catalog.to_regclass(:name) AND polname=:policy)"""),
        {'name': 'public.' + TABLE, 'policy': POLICY}).scalar_one()
    privileges = conn.execute(text("""SELECT EXISTS(
        SELECT 1 FROM pg_catalog.pg_class c,
          LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
        WHERE c.oid=pg_catalog.to_regclass(:name) AND a.grantee=pg_catalog.to_regrole(:role)
        UNION ALL SELECT 1 FROM pg_catalog.pg_attribute col,
          LATERAL pg_catalog.aclexplode(col.attacl) a
        WHERE col.attrelid=pg_catalog.to_regclass(:name) AND a.grantee=pg_catalog.to_regrole(:role))"""),
        {'name': 'public.' + TABLE, 'role': EVALUATOR}).scalar_one()
    # Explicit ACLs alone miss privileges inherited from PUBLIC. Existing
    # permissive PUBLIC read policies could also OR away the new tenant filter.
    effective_privileges = conn.execute(text("""SELECT
        pg_catalog.has_table_privilege(:role,:name,
          'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
        OR pg_catalog.has_any_column_privilege(:role,:name,
          'SELECT,INSERT,UPDATE,REFERENCES')"""),
        {'name': 'public.' + TABLE, 'role': EVALUATOR}).scalar_one()
    read_policy = conn.execute(text("""SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_policy
        WHERE polrelid=pg_catalog.to_regclass(:name) AND polcmd IN ('r','*')
          AND (0::oid=ANY(polroles) OR pg_catalog.to_regrole(:role)::oid=ANY(polroles)))"""),
        {'name': 'public.' + TABLE, 'role': EVALUATOR}).scalar_one()
    if not role or not table or collision or privileges or effective_privileges or read_policy:
        raise RuntimeError('EVALUATOR_JUDGE_READ_BOUNDARY_DRIFT')
    conn.exec_driver_sql(f'GRANT SELECT ({",".join(COLUMNS)}) ON public.{TABLE} TO {EVALUATOR}')
    conn.exec_driver_sql(f"""CREATE POLICY {POLICY} ON public.{TABLE}
        FOR SELECT TO {EVALUATOR} USING (
          org_id='org-org' AND project_id='dev-project'
          AND org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    if previous.original_seals(conn) != seals or previous.function_shape(conn, previous.ENTRY) != runtime:
        raise RuntimeError('EVALUATOR_JUDGE_READ_ORIGINAL_SEAL_CHANGED')


def downgrade():
    raise RuntimeError('EVALUATOR_JUDGE_READ_REQUIRES_FORWARD_RECOVERY')
