"""Bound formal evaluation to original authorities and one atomic transaction.

No LOGIN provisioning, business activation, history backfill or new fact store.
"""
from alembic import op

revision = 'a0v_144'
down_revision = 'a0v_143'
branch_labels = depends_on = None
EVALUATOR = 'aos_aip_binding_evaluator'
MODEL_KINDS = ('provider_instance', 'registered_model', 'runtime_policy',
               'model_route', 'model_price_snapshot')
SCOPED_READ = (
    'meta_membership', 'bundle_installation', 'bundle_installation_revision',
    'bundle_composition', 'bundle_composition_lock',
    'aip_evidence_bundle_revision', 'aip_evidence_bundle_build_provenance',
    'aip_evidence_bundle_revoke_event', 'aip_production_contract_receipt',
    'aip_action_withdrawal_event', 'aip_license_source_issuance',
    'aip_license_source_head', 'aip_license_source_initialization_fence',
    'aip_budget_cost_proposal', 'aip_budget_cost_proposal_receipt',
    'aip_budget_cost_decision', 'aip_budget_cost_revocation',
    'aip_budget_cost_issuer_receipt', 'aip_budget_receipt',
    'aip_budget_cost_runtime_fence', 'aip_budget_head', 'aip_budget_revision',
    'aip_budget_reservation', 'aip_model_eval_budget_reservation',
    'aip_runtime_guard_policy_head', 'aip_runtime_guard_policy_revision',
    'aip_network_policy_head', 'aip_network_policy_revision',
    'aip_model_governance_policy_head', 'aip_model_governance_policy_revision',
    'aip_eval_contract_head', 'aip_eval_contract_revision',
    'aip_eval_suite_revision', 'aip_publication_event',
    'aip_release_gate_decision', 'aip_eval_dataset_revision',
    'aip_provider_health_observation', 'aip_model_capacity_pool_head',
    'aip_model_capacity_pool_revision', 'aip_model_capacity_reservation',
    'aip_capability_binding', 'aip_agent_registry_receipt',
    'aip_binding_evaluation_proof',
) + tuple(f'aip_{kind}_{suffix}' for kind in MODEL_KINDS for suffix in ('head', 'revision'))
GLOBAL_READ = ('meta_object_type', 'meta_action_type', 'asset_bundle',
               'asset_bundle_version', 'asset_bundle_artifact', 'asset_bundle_evidence',
               'aip_capability_revision')
LOCK_COLUMNS = (
    ('meta_membership', 'subject'), ('bundle_installation', 'installation_id'),
    ('meta_object_type', 'id'), ('meta_action_type', 'id'),
    ('aip_action_proposal', 'proposal_id'), ('aip_action_draft', 'draft_id'),
    ('aip_action_approval_event', 'approval_event_id'),
    ('asset_bundle_version', 'version_pk'), ('asset_bundle_evidence', 'version_pk'),
    ('aip_budget_cost_runtime_fence', 'version'), ('aip_budget_head', 'budget_id'),
    ('aip_runtime_guard_policy_head', 'policy_id'), ('aip_network_policy_head', 'policy_id'),
    ('aip_model_governance_policy_head', 'policy_id'),
    ('aip_eval_contract_head', 'contract_id'), ('aip_model_capacity_pool_head', 'pool_id'),
) + tuple((f'aip_{kind}_head', f'{kind}_id') for kind in MODEL_KINDS)
BINDING_UPDATE_COLUMNS = (
    'provider_ref', 'model_route_ref', 'runtime_policy_ref', 'eval_gate_ref',
    'eval_contract_ref', 'license_evidence_refs', 'data_dependency_refs',
    'tool_dependency_refs', 'budget_policy_ref', 'allow_degraded',
    'dependency_snapshot_hash', 'operational_readiness', 'readiness_reasons',
    'last_evaluated_at', 'readiness_expires_at', 'version', 'updated_at',
)


def upgrade() -> None:
    op.execute(f"""DO $$ DECLARE r record; BEGIN
      SELECT * INTO r FROM pg_catalog.pg_roles WHERE rolname='{EVALUATOR}';
      IF NOT FOUND THEN
        CREATE ROLE {EVALUATOR} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB
          NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
        OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls THEN
        RAISE EXCEPTION 'BINDING_EVALUATOR_RESERVED_IDENTITY_DRIFT' USING ERRCODE='42501';
      END IF;
      IF EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='{EVALUATOR}'::regrole
        OR member='{EVALUATOR}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_class WHERE relowner='{EVALUATOR}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner='{EVALUATOR}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a
            WHERE a.grantee='{EVALUATOR}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a
            WHERE a.grantee='{EVALUATOR}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a
            WHERE a.grantee='{EVALUATOR}'::regrole) THEN
        RAISE EXCEPTION 'BINDING_EVALUATOR_RESERVED_IDENTITY_DRIFT' USING ERRCODE='42501';
      END IF;
    END $$""")
    op.execute(f'GRANT USAGE ON SCHEMA public TO {EVALUATOR}')
    op.execute('CREATE UNIQUE INDEX uq_binding_evaluation_proof_version_a0v144 '
               'ON public.aip_binding_evaluation_proof(org_id,project_id,binding_id,binding_version)')
    tenant = ("org_id='org-org' AND project_id='dev-project' AND "
              "org_id=NULLIF(current_setting('aos.org_id',true),'') AND "
              "project_id=NULLIF(current_setting('aos.project_id',true),'')")
    for table in SCOPED_READ:
        # Some legacy catalog tables carry policies but never enabled RLS.
        # Preserve their prior behavior for other identities while requiring
        # this new reader to obey its tenant policy, even under a PUBLIC policy.
        legacy = f"current_user<>'{EVALUATOR}' AND session_user<>'{EVALUATOR}'"
        op.execute(f"""DO $$ BEGIN
          IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid='public.{table}'::regclass) THEN
            CREATE POLICY binding_evaluator_legacy_a0v144 ON public.{table} TO PUBLIC
              USING ({legacy}) WITH CHECK ({legacy});
          END IF;
        END $$""")
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY binding_evaluator_restrict_a0v144 ON public.{table} '
                   f'AS RESTRICTIVE TO PUBLIC USING (({legacy}) OR ({tenant})) '
                   f'WITH CHECK (({legacy}) OR ({tenant}))')
        op.execute(f'GRANT SELECT ON public.{table} TO {EVALUATOR}')
        op.execute(f'CREATE POLICY binding_evaluator_scope_a0v144 ON public.{table} '
                   f'TO {EVALUATOR} USING ({tenant}) WITH CHECK ({tenant})')
    for table in GLOBAL_READ:
        op.execute(f'GRANT SELECT ON public.{table} TO {EVALUATOR}')
    source = "action_type_id='aip_issue_source_license' AND action_type_snapshot->>'id'='aip_issue_source_license'"
    op.execute('ALTER TABLE public.aip_action_proposal ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.aip_action_proposal FORCE ROW LEVEL SECURITY')
    op.execute(f'CREATE POLICY binding_evaluator_restrict_a0v144 ON public.aip_action_proposal '
               f'AS RESTRICTIVE TO PUBLIC USING (({legacy}) OR ({tenant} AND {source})) '
               f'WITH CHECK (({legacy}) OR ({tenant} AND {source}))')
    op.execute(f'GRANT SELECT ON public.aip_action_proposal TO {EVALUATOR}')
    op.execute(f'CREATE POLICY binding_evaluator_source_a0v144 ON public.aip_action_proposal '
               f'TO {EVALUATOR} USING ({tenant} AND {source}) WITH CHECK ({tenant} AND {source})')
    for table in ('aip_action_draft', 'aip_action_approval_event'):
        related = (f'EXISTS(SELECT 1 FROM public.aip_action_proposal p WHERE '
                   f'p.org_id={table}.org_id AND p.project_id={table}.project_id '
                   f'AND p.proposal_id={table}.proposal_id AND {source})')
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY binding_evaluator_restrict_a0v144 ON public.{table} '
                   f'AS RESTRICTIVE TO PUBLIC USING (({legacy}) OR ({tenant} AND {related})) '
                   f'WITH CHECK (({legacy}) OR ({tenant} AND {related}))')
        op.execute(f'GRANT SELECT ON public.{table} TO {EVALUATOR}')
        op.execute(f'CREATE POLICY binding_evaluator_source_related_a0v144 ON public.{table} '
                   f'TO {EVALUATOR} USING ({tenant} AND {related}) WITH CHECK ({tenant} AND {related})')
    for table, column in LOCK_COLUMNS:
        op.execute(f'GRANT UPDATE({column}) ON public.{table} TO {EVALUATOR}')
    # The shared Health API initializes a neutral row under its own definer.
    # Restrict the originating evaluator session without granting table access.
    op.execute('CREATE POLICY binding_evaluator_restrict_a0v144 ON public.aip_provider_health_epoch '
               f'AS RESTRICTIVE TO PUBLIC USING (({legacy}) OR ({tenant})) '
               f'WITH CHECK (({legacy}) OR ({tenant}))')
    op.execute(f"""CREATE FUNCTION public.binding_evaluator_read_lock_only_a0v144()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF current_user='{EVALUATOR}' OR session_user='{EVALUATOR}' THEN
          RAISE EXCEPTION 'BINDING_EVALUATOR_READ_LOCK_ONLY' USING ERRCODE='42501';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.binding_evaluator_read_lock_only_a0v144() FROM PUBLIC')
    for table, _ in LOCK_COLUMNS:
        op.execute(f'CREATE TRIGGER aaa_binding_evaluator_read_lock_only_a0v144 '
                   f'BEFORE INSERT OR UPDATE OR DELETE ON public.{table} FOR EACH ROW '
                   'EXECUTE FUNCTION public.binding_evaluator_read_lock_only_a0v144()')
    op.execute(f"GRANT UPDATE({','.join(BINDING_UPDATE_COLUMNS)}) ON public.aip_capability_binding TO {EVALUATOR}")
    op.execute(f'GRANT INSERT ON public.aip_agent_registry_receipt,public.aip_binding_evaluation_proof TO {EVALUATOR}')
    for signature in (
        'public.aos_license_source_initialization_lock(text,text,text,bigint,text,boolean)',
        'public.aos_license_source_lock(text,text,text,bigint,text,boolean)',
        'public.aos_provider_health_epoch_lock(text,text,jsonb,boolean)',
        'public.canonical_asset_registry_jsonb(jsonb)',
    ):
        op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO {EVALUATOR}')

    op.execute(f"""CREATE FUNCTION public.binding_evaluator_write_guard_a0v144()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF current_user='{EVALUATOR}' OR session_user='{EVALUATOR}' THEN
          IF current_user<>'{EVALUATOR}' OR session_user<>'{EVALUATOR}'
            OR current_setting('transaction_isolation')<>'serializable'
            OR NEW.org_id<>'org-org' OR NEW.project_id<>'dev-project'
            OR NEW.org_id IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
            OR NEW.project_id IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
            RAISE EXCEPTION 'BINDING_EVALUATOR_TRANSACTION_REQUIRED' USING ERRCODE='42501';
          END IF;
          IF TG_TABLE_NAME='aip_capability_binding' THEN
            IF NEW.version<>OLD.version+1 OR NEW.status IS DISTINCT FROM OLD.status
              OR OLD.status NOT IN ('provisioning','active','suspended') THEN
              RAISE EXCEPTION 'BINDING_EVALUATOR_CAS_REQUIRED' USING ERRCODE='23514';
            END IF;
          ELSIF TG_TABLE_NAME='aip_agent_registry_receipt' THEN
            IF NEW.operation<>'capability_binding.evaluate' OR NEW.status<>'applied' THEN
              RAISE EXCEPTION 'BINDING_EVALUATOR_RECEIPT_OPERATION_REQUIRED' USING ERRCODE='42501';
            END IF;
          END IF;
        ELSIF TG_TABLE_NAME='aip_binding_evaluation_proof' AND current_user<>(
          SELECT r.rolname FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner WHERE c.oid=TG_RELID) THEN
          RAISE EXCEPTION 'BINDING_EVALUATOR_INDEPENDENT_IDENTITY_REQUIRED' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.binding_evaluator_write_guard_a0v144() FROM PUBLIC')
    for table, event in (('aip_capability_binding', 'UPDATE'),
                         ('aip_agent_registry_receipt', 'INSERT'),
                         ('aip_binding_evaluation_proof', 'INSERT')):
        op.execute(f'CREATE TRIGGER binding_evaluator_write_guard_a0v144 BEFORE {event} '
                   f'ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.binding_evaluator_write_guard_a0v144()')

    op.execute(f"""CREATE FUNCTION public.binding_evaluator_atomic_triple_a0v144()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
      SET search_path=pg_catalog,public,pg_temp AS $$ DECLARE
        p public.aip_binding_evaluation_proof%ROWTYPE;
        b public.aip_capability_binding%ROWTYPE;
        r public.aip_agent_registry_receipt%ROWTYPE;
        i public.bundle_installation%ROWTYPE;
        live_now timestamptz := clock_timestamp();
      BEGIN
        -- Legacy preview and privileged maintenance do not certify formal readiness.
        IF current_user<>'{EVALUATOR}' AND session_user<>'{EVALUATOR}' THEN RETURN NEW; END IF;
        IF TG_TABLE_NAME='aip_capability_binding' THEN
          SELECT * INTO p FROM public.aip_binding_evaluation_proof WHERE org_id=NEW.org_id
            AND project_id=NEW.project_id AND binding_id=NEW.binding_id AND binding_version=NEW.version;
        ELSE
          SELECT * INTO p FROM public.aip_binding_evaluation_proof WHERE org_id=NEW.org_id
            AND project_id=NEW.project_id AND receipt_id=NEW.receipt_id;
        END IF;
        IF p.proof_id IS NULL THEN
          RAISE EXCEPTION 'BINDING_EVALUATOR_ATOMIC_TRIPLE_REQUIRED' USING ERRCODE='23514';
        END IF;
        SELECT * INTO b FROM public.aip_capability_binding WHERE org_id=p.org_id
          AND project_id=p.project_id AND binding_id=p.binding_id;
        SELECT * INTO r FROM public.aip_agent_registry_receipt WHERE org_id=p.org_id
          AND project_id=p.project_id AND receipt_id=p.receipt_id;
        SELECT * INTO i FROM public.bundle_installation WHERE org_id=p.org_id
          AND project_id=p.project_id AND installation_id=p.installation_id;
        IF b.binding_id IS NULL OR r.receipt_id IS NULL OR i.installation_id IS NULL
          OR b.version IS DISTINCT FROM p.binding_version
          OR b.dependency_snapshot_hash IS DISTINCT FROM p.legacy_dependency_hash
          OR b.operational_readiness IS DISTINCT FROM 'available'
          OR b.last_evaluated_at IS DISTINCT FROM p.checked_at
          OR b.readiness_expires_at IS DISTINCT FROM p.valid_until
          OR r.operation IS DISTINCT FROM 'capability_binding.evaluate' OR r.status IS DISTINCT FROM 'applied'
          OR r.resource_ref->>'resourceType' IS DISTINCT FROM 'CapabilityBinding'
          OR r.resource_ref->>'resourceId' IS DISTINCT FROM p.binding_id
          OR r.result_ref->>'resourceType' IS DISTINCT FROM 'CapabilityBindingReadiness'
          OR r.result_ref->>'resourceId' IS DISTINCT FROM p.binding_id
          OR r.result_ref->>'revision' IS DISTINCT FROM p.binding_version::text
          OR r.resource_ref->>'authority' IS DISTINCT FROM 'postgresql'
          OR r.result_ref->>'authority' IS DISTINCT FROM 'postgresql'
          OR r.created_at IS DISTINCT FROM p.checked_at
          OR NOT EXISTS(SELECT 1 FROM public.aip_capability_binding bc
              JOIN public.aip_agent_registry_receipt rc ON rc.org_id=bc.org_id AND rc.project_id=bc.project_id
              JOIN public.aip_binding_evaluation_proof pc ON pc.org_id=bc.org_id AND pc.project_id=bc.project_id
                AND pc.binding_id=bc.binding_id AND pc.receipt_id=rc.receipt_id
              WHERE bc.org_id=p.org_id AND bc.project_id=p.project_id AND bc.binding_id=p.binding_id
                AND pc.proof_id=p.proof_id AND bc.xmin=pg_current_xact_id()::xid
                AND rc.xmin=pg_current_xact_id()::xid AND pc.xmin=pg_current_xact_id()::xid)
          OR NOT (p.checked_at<=live_now AND live_now<p.valid_until)
          OR i.etag_version IS DISTINCT FROM p.installation_etag
          OR i.current_revision IS DISTINCT FROM i.active_revision OR i.active_revision IS NULL
          OR p.facts->'Installation' IS DISTINCT FROM jsonb_build_object('installationId',i.installation_id::text,
              'revision',i.current_revision,'etag',i.etag_version)
          OR NOT p.facts ?& ARRAY['Provider','Model','Policy','Route','Eval','Health','Capacity','Price',
                                  'Source','Budget','Installation','Owners']
          OR jsonb_typeof(p.facts->'Source') IS DISTINCT FROM 'array'
          OR jsonb_typeof(p.facts->'Owners') IS DISTINCT FROM 'array'
          OR jsonb_typeof(p.facts->'Budget') IS DISTINCT FROM 'object'
          OR p.facts->'Source'='[]'::jsonb OR p.facts->'Owners'='[]'::jsonb OR p.facts->'Budget'='{{}}'::jsonb
          OR EXISTS(SELECT 1 FROM jsonb_each(p.facts) f WHERE f.key=ANY(
              ARRAY['Provider','Model','Policy','Route','Eval','Health','Capacity','Price'])
              AND (jsonb_typeof(f.value)<>'object' OR f.value='{{}}'::jsonb))
          OR p.facts_hash IS DISTINCT FROM encode(public.digest(
              convert_to(public.canonical_asset_registry_jsonb(p.facts),'UTF8'),'sha256'),'hex') THEN
          RAISE EXCEPTION 'BINDING_EVALUATOR_ATOMIC_TRIPLE_REQUIRED' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.binding_evaluator_atomic_triple_a0v144() FROM PUBLIC')
    for table, label, event in (('aip_capability_binding', 'binding', 'UPDATE'),
                                ('aip_agent_registry_receipt', 'receipt', 'INSERT'),
                                ('aip_binding_evaluation_proof', 'proof', 'INSERT')):
        op.execute(f'CREATE CONSTRAINT TRIGGER binding_evaluator_atomic_{label}_a0v144 '
                   f'AFTER {event} ON public.{table} DEFERRABLE INITIALLY DEFERRED '
                   'FOR EACH ROW EXECUTE FUNCTION public.binding_evaluator_atomic_triple_a0v144()')


def downgrade() -> None:
    raise RuntimeError('formal evaluator proof history cannot be silently erased')
