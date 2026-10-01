"""Immutable, tenant-scoped first Model Eval application; no execution grant."""

from alembic import op

revision = "a0v_133"
down_revision = "a0v_132"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.meta_object_type WHERE id='ModelEvalRequest')
         OR EXISTS(SELECT 1 FROM public.meta_action_type WHERE id='aip_request_model_eval') THEN
        RAISE EXCEPTION 'MODEL_EVAL_METADATA_ALREADY_PRESENT' USING ERRCODE='23505';
      END IF;
    END $$""")
    op.execute("""CREATE FUNCTION public.model_eval_metadata_a0v133()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE object_name text; protected_id text; owner_name text; BEGIN
        object_name := CASE WHEN TG_TABLE_NAME='meta_object_type'
          THEN 'ModelEvalRequest' ELSE 'aip_request_model_eval' END;
        protected_id := CASE WHEN TG_OP='DELETE' THEN OLD.id ELSE NEW.id END;
        IF protected_id=object_name OR (TG_OP='UPDATE' AND OLD.id=object_name) THEN
          SELECT pg_get_userbyid(relowner) INTO owner_name FROM pg_class
            WHERE oid=format('public.%I',TG_TABLE_NAME)::regclass;
          IF current_user IS DISTINCT FROM owner_name THEN
            RAISE EXCEPTION 'MODEL_EVAL_METADATA_RESERVED' USING ERRCODE='42501';
          END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.model_eval_metadata_a0v133() FROM PUBLIC")
    for table in ("meta_object_type", "meta_action_type"):
        op.execute(f"""CREATE TRIGGER model_eval_metadata_a0v133
          BEFORE INSERT OR UPDATE OR DELETE ON public.{table}
          FOR EACH ROW EXECUTE FUNCTION public.model_eval_metadata_a0v133()""")
    op.execute("""INSERT INTO public.meta_object_type
      (id,name,description,published,properties,required_markings)
      VALUES('ModelEvalRequest','模型首次评测申请','仅供独立审批的不可执行申请',TRUE,'[]','[]')""")
    op.execute("""INSERT INTO public.meta_action_type
      (id,name,object_type,parameters,required_markings,submission_criteria)
      VALUES('aip_request_model_eval','申请模型首次评测','ModelEvalRequest','[]','[]','[]')""")
    op.execute("""CREATE TABLE aip_model_eval_request (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL,
      request_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
      request_hash TEXT NOT NULL, request_json JSONB NOT NULL,
      source_ref JSONB NOT NULL, target_ref JSONB NOT NULL,
      expected_head_version BIGINT NOT NULL,
      eval_contract_ref JSONB NOT NULL, suite_ref JSONB NOT NULL,
      provider_ref JSONB NOT NULL, price_ref JSONB NOT NULL,
      quota_policy_ref JSONB NOT NULL, budget_policy_ref JSONB NOT NULL,
      purpose TEXT NOT NULL, currency TEXT NOT NULL,
      upper_bound_minor BIGINT NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
      created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (org_id,project_id,request_id),
      UNIQUE (org_id,project_id,idempotency_key),
      FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id),
      CHECK (request_hash ~ '^[0-9a-f]{64}$'),
      CHECK (expected_head_version >= 1 AND upper_bound_minor BETWEEN 1 AND 100000000),
      CHECK (purpose='quality-eval' AND currency='CNY' AND expires_at>created_at),
      CHECK (length(request_id)>0 AND length(idempotency_key)>0 AND length(created_by)>0),
      CHECK (jsonb_typeof(request_json)='object'),
      CHECK (request_json->'sourceRef'=source_ref AND request_json->'targetRef'=target_ref
         AND request_json->'tenant'->>'orgId'=org_id
         AND request_json->'tenant'->>'projectId'=project_id
         AND request_json->'evalContractRef'=eval_contract_ref
         AND request_json->'suiteRef'=suite_ref AND request_json->'providerRef'=provider_ref
         AND request_json->'priceRef'=price_ref
         AND request_json->'quotaPolicyRef'=quota_policy_ref
         AND request_json->'budgetPolicyRef'=budget_policy_ref
         AND request_json->'expectedHeadVersion'=to_jsonb(expected_head_version)
         AND request_json->>'purpose'=purpose AND request_json->>'currency'=currency
         AND request_json->'upperBoundMinor'=to_jsonb(upper_bound_minor)
         AND (request_json->>'expiresAt')::timestamptz=expires_at)
    )""")
    op.execute("ALTER TABLE aip_model_eval_request ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_model_eval_request FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_aip_model_eval_request_a0v133
      ON aip_model_eval_request TO aos_runtime
      USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
         AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
         AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE TRIGGER trg_aip_model_eval_request_append_only
      BEFORE UPDATE OR DELETE ON aip_model_eval_request
      FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER trg_aip_model_eval_request_truncate_guard
      BEFORE TRUNCATE ON aip_model_eval_request
      FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("REVOKE ALL ON aip_model_eval_request FROM PUBLIC,aos_runtime")
    op.execute("GRANT SELECT,INSERT ON aip_model_eval_request TO aos_runtime")


def downgrade() -> None:
    raise RuntimeError("formal Model Eval application evidence cannot be silently removed")
