"""Tenant/installation scoped internal bootstrap definition, admitted by event enable."""
from alembic import op
revision='a0v_061'
down_revision='a0v_060'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    CREATE TABLE public.ecommerce_installed_bootstrap_action(
      org_id text NOT NULL,project_id text NOT NULL,entry_id uuid NOT NULL,
      installation_id uuid NOT NULL,generation uuid NOT NULL,execution_epoch bigint NOT NULL CHECK(execution_epoch>0),
      action_id text NOT NULL CHECK(action_id='ecommerce_analysis_bootstrap'),
      control_receipt_id uuid NOT NULL,payload jsonb NOT NULL,content_hash text NOT NULL
        CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      PRIMARY KEY(org_id,project_id,entry_id),
      UNIQUE(org_id,project_id,installation_id,generation,execution_epoch,action_id),
      FOREIGN KEY(org_id,project_id,installation_id,generation)
        REFERENCES public.extension_runtime_binding(org_id,project_id,installation_id,generation),
      FOREIGN KEY(org_id,project_id,control_receipt_id)
        REFERENCES public.ecommerce_product_event_control_receipt(org_id,project_id,receipt_id)
    );
    ALTER TABLE public.ecommerce_installed_bootstrap_action ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.ecommerce_installed_bootstrap_action FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON public.ecommerce_installed_bootstrap_action
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON public.ecommerce_installed_bootstrap_action FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT SELECT ON public.ecommerce_installed_bootstrap_action TO aos_runtime,aos_extension_maintainer;
    CREATE FUNCTION public.installed_bootstrap_action_immutable_a0v_061()
    RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      RAISE EXCEPTION 'installed bootstrap action history is immutable' USING ERRCODE='55000'; END $$;
    CREATE TRIGGER bootstrap_action_immutable BEFORE UPDATE OR DELETE ON public.ecommerce_installed_bootstrap_action
      FOR EACH ROW EXECUTE FUNCTION public.installed_bootstrap_action_immutable_a0v_061();
    CREATE TRIGGER bootstrap_action_no_truncate BEFORE TRUNCATE ON public.ecommerce_installed_bootstrap_action
      FOR EACH STATEMENT EXECUTE FUNCTION public.installed_bootstrap_action_immutable_a0v_061();

    CREATE FUNCTION public.install_bootstrap_action_a0v_061(p_receipt uuid)
    RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_control record;v_binding record;v_runtime record;v_old record;
      v_definition jsonb;v_payload jsonb;v_hash text;v_id uuid:=gen_random_uuid();
    BEGIN
      IF v_org IS NULL OR v_project IS NULL OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
      THEN RAISE EXCEPTION 'scoped runtime admission required' USING ERRCODE='42501'; END IF;
      SELECT * INTO v_control FROM public.ecommerce_product_event_control_receipt
        WHERE org_id=v_org AND project_id=v_project AND receipt_id=p_receipt;
      IF NOT FOUND OR v_control.command->>'intent' IS DISTINCT FROM 'enable'
        OR v_control.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(v_control.authority),'UTF8')),'hex')
        OR v_control.request_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(v_control.command),'UTF8')),'hex')
        OR v_control.authority->'command' IS DISTINCT FROM v_control.command
        OR v_control.authority->>'actor' IS DISTINCT FROM v_control.actor
      THEN RAISE EXCEPTION 'verified enable receipt required' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_binding FROM public.automation_schedule_binding WHERE org_id=v_org AND project_id=v_project
        AND policy_id=v_control.policy_id AND policy_revision=v_control.policy_revision FOR UPDATE;
      IF NOT FOUND OR NOT v_binding.enabled OR NOT v_binding.approved OR v_binding.cadence<>'event'
        OR v_binding.operation_id<>'ecommerce_growth_analysis_advance'
        OR to_jsonb(v_binding) IS DISTINCT FROM v_control.authority->'binding'
      THEN RAISE EXCEPTION 'current exact enabled analysis binding required' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_runtime FROM public.extension_runtime_binding WHERE org_id=v_org AND project_id=v_project
        AND installation_id=v_binding.installation_id AND generation=v_binding.generation FOR UPDATE;
      IF NOT FOUND OR NOT v_runtime.enabled OR v_runtime.operation_fence
        OR v_runtime.execution_epoch<>v_binding.execution_epoch OR v_runtime.desired_state<>'enabled'
        OR v_runtime.observed_state<>'ready'
      THEN RAISE EXCEPTION 'current installed runtime required' USING ERRCODE='55000'; END IF;
      IF NOT EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding
          WHERE org_id=v_org AND project_id=v_project AND operation_id='ecommerce_growth_analysis_advance'
          AND handler_kind='extension' AND installation_id=v_binding.installation_id AND generation=v_binding.generation
          AND execution_epoch=v_binding.execution_epoch AND NOT operation_fence)
      THEN RAISE EXCEPTION 'current analysis dispatch required' USING ERRCODE='55000'; END IF;
      v_definition:=jsonb_build_object('id','ecommerce_analysis_bootstrap','name','初始化分析承接',
        'objectType','Task','parameters','[]'::jsonb,'requiredMarkings','[]'::jsonb,'submissionCriteria','[]'::jsonb);
      SELECT * INTO v_old FROM public.ecommerce_installed_bootstrap_action WHERE org_id=v_org AND project_id=v_project
        AND installation_id=v_binding.installation_id AND generation=v_binding.generation
        AND execution_epoch=v_binding.execution_epoch AND action_id='ecommerce_analysis_bootstrap';
      IF FOUND THEN
        IF v_old.payload->'definition' IS DISTINCT FROM v_definition
          OR v_old.payload->'configRef' IS DISTINCT FROM v_runtime.config_ref
          OR v_old.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(v_old.payload),'UTF8')),'hex')
        THEN RAISE EXCEPTION 'installed action definition drift' USING ERRCODE='40001'; END IF;
        RETURN v_old.entry_id;
      END IF;
      v_payload:=jsonb_build_object('schemaVersion','aos.ecommerce.installed-bootstrap-action/v1',
        'tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),'entryId',v_id::text,
        'installationId',v_binding.installation_id::text,'generation',v_binding.generation::text,
        'executionEpoch',v_binding.execution_epoch,'configRef',v_runtime.config_ref,'definition',v_definition,
        'controlReceiptRef',jsonb_build_object('resourceType','EventPolicyControlReceipt',
          'resourceId',p_receipt::text,'revision',v_control.binding_revision,'contentHash',v_control.content_hash),
        'actor',v_control.actor,'createdAt',clock_timestamp(),
        'businessExecutionAuthorized',false,'externalEffectAuthorized',false);
      v_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_payload),'UTF8')),'hex');
      INSERT INTO public.ecommerce_installed_bootstrap_action VALUES(v_org,v_project,v_id,
        v_binding.installation_id,v_binding.generation,v_binding.execution_epoch,'ecommerce_analysis_bootstrap',p_receipt,v_payload,v_hash);
      RETURN v_id;
    END $$;
    REVOKE ALL ON FUNCTION public.install_bootstrap_action_a0v_061(uuid) FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION public.install_bootstrap_action_a0v_061(uuid) TO aos_runtime;
    ''')


def downgrade():
    raise RuntimeError('installed action history must be retained')
