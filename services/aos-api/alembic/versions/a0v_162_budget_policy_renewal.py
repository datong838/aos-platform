"""Closed renewal journal/identity foundation; full producer/consumer still pending.

This candidate must not be deployed until the complete A-wave is reviewed.
No login enablement, credential, approval, Source or Provider activation occurs.
"""
import json
from pathlib import Path
from alembic import op

revision = 'a0v_162'
down_revision = 'a0v_161'
branch_labels = depends_on = None
OWNERS = ('aos_budget_renewal_proposal_owner', 'aos_budget_renewal_issuer_owner',
          'aos_budget_renewal_publish_owner')
CALLERS = ('aos_budget_renewal_maker_call', 'aos_budget_renewal_issuer_call',
           'aos_budget_renewal_consumer_call')
JOURNALS = ('aip_budget_policy_renewal_proposal', 'aip_budget_policy_renewal_decision',
            'aip_budget_policy_renewal_receipt')
ORIGINAL = ('aip_model_governance_policy_head', 'aip_model_governance_policy_revision',
            'aip_budget_head', 'aip_budget_revision', 'aip_provider_instance_head',
            'aip_provider_instance_revision', 'meta_membership')
FUNCTIONS = {
    'public.aip_renewal_relation_shape_a0v_162(oid)': (OWNERS[0], False),
    'public.aip_renewal_profile_a0v_162(text)': (OWNERS[0], False),
    'public.aip_renewal_checker_member_a0v_162()': (OWNERS[1], True),
    'public.aip_renewal_source_a0v_162(jsonb,text)': (OWNERS[0], False),
    'public.aip_renewal_proposal_command_a0v_162(jsonb)': (OWNERS[0], False),
    'public.aip_renewal_propose_a0v_162(jsonb)': (OWNERS[0], True),
    'public.aip_renewal_reconcile_a0v_162(jsonb,text,text)': (OWNERS[2], True),
    'public.aip_renewal_issuer_command_a0v_162(jsonb,text)': (OWNERS[1], False),
    'public.aip_renewal_issuer_fact_a0v_162(jsonb,text,boolean)': (OWNERS[1], False),
    'public.aip_renewal_issuer_write_a0v_162(jsonb,text,text)': (OWNERS[1], False),
    'public.aip_renewal_decide_a0v_162(jsonb,text)': (OWNERS[1], True),
    'public.aip_renewal_revoke_a0v_162(jsonb,text)': (OWNERS[1], True),
    'public.aip_renewal_consume_command_a0v_162(jsonb)': (OWNERS[2], False),
    'public.aip_renewal_consume_fact_a0v_162(jsonb,boolean)': (OWNERS[2], False),
    'public.aip_renewal_consume_history_a0v_162(jsonb)': (OWNERS[2], False),
    'public.aip_renewal_assert_insert_a0v_162(text,text,text,bigint,text,jsonb,text,timestamp with time zone,timestamp with time zone,timestamp with time zone)': (OWNERS[2], False),
    'public.aip_renewal_complete_receipt_a0v_162()': (OWNERS[2], True),
    'public.aip_renewal_consume_a0v_162(jsonb)': (OWNERS[2], True),
}
SEALED_ORIGINAL_FUNCTIONS = (
    'public.aip_budget_cost_hash_a0v_126(jsonb)',
    'public.canonical_asset_registry_jsonb(jsonb)',
    'public.guard_aip4_append_only()',
    'public.aip_cost_configuration_write_guard_a0v_128()',
)
SCOPE = """org_id='org-org' AND project_id='dev-project'
 AND org_id=NULLIF(current_setting('aos.org_id',true),'')
 AND project_id=NULLIF(current_setting('aos.project_id',true),'')"""


def upgrade():
    # Do not repair or switch existing isolation while installing a candidate.
    for table in ORIGINAL:
        op.execute(f"""DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_class
          WHERE oid='public.{table}'::regclass AND relrowsecurity AND relforcerowsecurity) THEN
          RAISE EXCEPTION 'RENEWAL_ORIGINAL_FORCE_RLS_REQUIRED'; END IF; END $$""")
    for role in OWNERS + CALLERS:
        # A collision is a reconciliation gate, never silently alter a role.
        op.execute(f'CREATE ROLE {role} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS '
                   'NOCREATEDB NOCREATEROLE NOREPLICATION')
        op.execute(f'GRANT USAGE ON SCHEMA public TO {role}')
    source = Path(__file__).resolve().parents[2] / 'aos_api/aip_budget_policy_renewal_authority.sql'
    op.get_bind().exec_driver_sql(source.read_text().replace('%', '%%'))
    for table in JOURNALS:
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON public.{table} FROM PUBLIC')
        op.execute(f'CREATE TRIGGER renewal_immutable_update BEFORE UPDATE OR DELETE ON public.{table} '
                   'FOR EACH ROW EXECUTE FUNCTION public.guard_aip4_append_only()')
        op.execute(f'CREATE TRIGGER renewal_immutable_truncate BEFORE TRUNCATE ON public.{table} '
                   'FOR EACH STATEMENT EXECUTE FUNCTION public.guard_aip4_append_only()')
    for table in ORIGINAL + JOURNALS:
        for owner in OWNERS:
            op.execute(f'GRANT SELECT ON public.{table} TO {owner}')
            op.execute(f'CREATE POLICY renewal_scope_a0v162_{owner.rsplit("_",1)[0].rsplit("_",1)[1]} '
                       f'ON public.{table} TO {owner} USING({SCOPE}) WITH CHECK({SCOPE})')
    # PostgreSQL row locks require one UPDATE column, even for immutable journals.
    for owner in OWNERS:
        for table, column in (('aip_budget_head', 'budget_id'),
                              ('aip_provider_instance_head', 'provider_instance_id'),
                              ('meta_membership', 'subject'),
                              (JOURNALS[0], 'proposal_id')):
            op.execute(f'GRANT UPDATE({column}) ON public.{table} TO {owner}')
        if owner != OWNERS[2]:
            op.execute(f'GRANT UPDATE(policy_id) ON public.aip_model_governance_policy_head TO {owner}')
    for owner in OWNERS[1:]:
        op.execute(f'GRANT UPDATE(decision_id) ON public.{JOURNALS[1]} TO {owner}')
    op.execute(f'GRANT INSERT ON public.{JOURNALS[0]} TO {OWNERS[0]}')
    op.execute(f'GRANT INSERT ON public.{JOURNALS[1]} TO {OWNERS[1]}')
    for owner in OWNERS:
        op.execute(f'GRANT INSERT ON public.{JOURNALS[2]} TO {owner}')
        op.execute(f'GRANT EXECUTE ON FUNCTION public.aip_budget_cost_hash_a0v_126(jsonb) TO {owner}')
    op.execute(f'GRANT INSERT ON public.aip_model_governance_policy_revision TO {OWNERS[2]}')
    op.execute(f'GRANT UPDATE(current_revision,version,updated_at) '
               f'ON public.aip_model_governance_policy_head TO {OWNERS[2]}')
    for signature, (owner, _definer) in FUNCTIONS.items():
        op.execute(f'ALTER FUNCTION {signature} OWNER TO {owner}')
        op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
        for reader in OWNERS:
            op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO {reader}')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aip_renewal_checker_member_a0v_162() TO {CALLERS[1]}')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aip_renewal_propose_a0v_162(jsonb) TO {CALLERS[0]}')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aip_renewal_reconcile_a0v_162(jsonb,text,text) TO {CALLERS[0]}')
    for signature in ('public.aip_renewal_reconcile_a0v_162(jsonb,text,text)',
                      'public.aip_renewal_decide_a0v_162(jsonb,text)',
                      'public.aip_renewal_revoke_a0v_162(jsonb,text)'):
        op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO {CALLERS[1]}')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aip_renewal_consume_a0v_162(jsonb) TO {CALLERS[2]}')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aip_renewal_reconcile_a0v_162(jsonb,text,text) TO {CALLERS[2]}')
    op.execute('CREATE CONSTRAINT TRIGGER renewal_consume_complete AFTER INSERT ON public.aip_budget_policy_renewal_receipt '
               'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.aip_renewal_complete_receipt_a0v_162()')
    # Seal only a new object's COMMENT; preserve every original COMMENT.
    conn = op.get_bind()
    functions = []
    for signature in tuple(FUNCTIONS) + SEALED_ORIGINAL_FUNCTIONS:
        row = conn.exec_driver_sql("""SELECT jsonb_build_object('signature',%s::text,
          'owner',pg_get_userbyid(proowner),'definer',prosecdef,'config',to_jsonb(proconfig),
          'acl',proacl::text,'bodySha256',encode(public.digest(convert_to(
          pg_get_functiondef(oid),'UTF8'),'sha256'),'hex')) FROM pg_proc WHERE oid=%s::regprocedure""",
                                  (signature, signature)).scalar_one()
        functions.append(row)
    relations = [conn.exec_driver_sql(
        'SELECT public.aip_renewal_relation_shape_a0v_162(%s::regclass)', ('public.' + name,)).scalar_one()
        for name in ORIGINAL + JOURNALS]
    seal = json.dumps({'schema': 'aos-renewal-schema-seal/v1', 'functions': functions,
                       'relations': relations}, separators=(',', ':'))
    conn.exec_driver_sql("COMMENT ON TABLE public.aip_budget_policy_renewal_proposal IS '"
                         + seal.replace("'", "''") + "'")


def downgrade():
    raise RuntimeError('renewal authority history cannot be removed; use explicit retirement')
