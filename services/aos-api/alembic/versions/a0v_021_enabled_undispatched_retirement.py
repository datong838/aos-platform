"""Retire enabled but never dispatched, exactly disabled released generations."""
from alembic import op
import sqlalchemy as sa

revision = 'a0v_021'
down_revision = 'a0v_020'
branch_labels = depends_on = None

BRANCH = """
        IF v_binding.config_ref IS NOT NULL
          AND EXISTS (SELECT 1 FROM public.extension_runtime_configuration c
            WHERE c.org_id=v_org AND c.project_id=v_project AND c.installation_id=p_installation_id
              AND c.generation=v_binding.generation
              AND c.configuration_id::text=v_binding.config_ref->>'configurationId'
              AND c.revision::text=v_binding.config_ref->>'revision'
              AND c.content_hash=v_binding.config_ref->>'hash')
          AND NOT EXISTS (SELECT 1 FROM public.extension_runtime_operation o
            WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=p_installation_id
              AND o.status NOT IN ('succeeded','failed','cancelled'))
          AND NOT EXISTS (SELECT 1 FROM public.extension_dispatch_cutover_operation c
            WHERE c.org_id=v_org AND c.project_id=v_project AND c.target_installation_id=p_installation_id)
          AND NOT EXISTS (SELECT 1 FROM public.extension_operation_dispatch_binding d
            WHERE d.org_id=v_org AND d.project_id=v_project AND d.installation_id=p_installation_id)
          AND NOT EXISTS (SELECT 1 FROM public.automation_occurrence o
            WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=p_installation_id)
          AND NOT EXISTS (SELECT 1 FROM public.extension_runtime_execution_attempt a
            WHERE a.org_id=v_org AND a.project_id=v_project AND a.installation_id=p_installation_id)
        THEN
          PERFORM 1 FROM public.extension_runtime_operation o
            WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=p_installation_id FOR UPDATE;
          SELECT o.operation_id,count(*) OVER() AS proof_count INTO v_enable
            FROM public.extension_runtime_operation o JOIN public.extension_runtime_event e
              USING(org_id,project_id,operation_id)
            WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=p_installation_id
              AND o.kind='enable' AND o.phase='succeeded' AND o.status='succeeded'
              AND e.type='enabled_committed'
              AND e.payload->>'installationId'=p_installation_id::text
              AND e.payload->>'generation'=v_binding.generation::text
              AND e.payload->'configRef'=v_binding.config_ref
              AND (e.payload->>'bindingRevision')::bigint < v_binding.revision
              AND (e.payload->>'executionEpoch')::bigint < v_binding.execution_epoch
              AND e.payload_hash='sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(e.payload),'UTF8')),'hex');
          IF NOT FOUND OR v_enable.proof_count<>1 THEN
            RAISE EXCEPTION 'exact successful enable proof required' USING ERRCODE='55000';
          END IF;
          SELECT d.operation_id AS disable_operation_id,count(*) OVER () AS proof_count
            INTO v_lifecycle
            FROM public.extension_runtime_operation d JOIN public.extension_runtime_event e
              ON e.org_id=d.org_id AND e.project_id=d.project_id AND e.operation_id=d.operation_id
            WHERE d.org_id=v_org AND d.project_id=v_project AND d.installation_id=p_installation_id
              AND d.kind='disable' AND d.status='succeeded' AND d.phase='succeeded'
              AND e.type='disabled_committed'
              AND e.payload=jsonb_build_object('installationId',p_installation_id::text,
                'generation',v_binding.generation::text,'bindingRevision',v_binding.revision,
                'executionEpoch',v_binding.execution_epoch,'resourcesRetained',true)
              AND e.payload_hash='sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(e.payload),'UTF8')),'hex');
          IF NOT FOUND OR v_lifecycle.proof_count<>1 THEN
            RAISE EXCEPTION 'exact undispatched disable proof required' USING ERRCODE='55000';
          END IF;
          PERFORM 1 FROM public.extension_runtime_resource_lease r
            JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
            WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=p_installation_id
            ORDER BY r.resource_id FOR UPDATE OF r;
          SELECT count(*),count(*) FILTER(WHERE NOT r.observed_release OR r.cleanup_state<>'released')
            INTO v_resource_count,v_unreleased_count
            FROM public.extension_runtime_resource_lease r
            JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
            WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=p_installation_id;
          IF v_resource_count<1 OR v_unreleased_count<>0 THEN
            RAISE EXCEPTION 'enabled undispatched resources not confirmed released' USING ERRCODE='55000';
          END IF;
          v_authority:=jsonb_build_object('orgId',v_org,'projectId',v_project,
            'installationId',p_installation_id::text,'generation',v_binding.generation::text,
            'installationRevision',p_expected_installation_revision,'bindingRevision',v_binding.revision+1,
            'retirementKind','enabled_undispatched','releasedResourceCount',v_resource_count,
            'configRef',v_binding.config_ref,'disableOperationId',v_lifecycle.disable_operation_id::text,
            'enableOperationId',v_enable.operation_id::text,'successfulEnableCount',1,'dispatchCount',0,'businessExecutionCount',0,'actor',BTRIM(p_actor));
          v_hash:='sha256:'||encode(sha256(convert_to(v_authority::text,'UTF8')),'hex');
          INSERT INTO public.extension_runtime_uninstall_receipt(
            org_id,project_id,receipt_id,installation_id,generation,disable_operation_id,activation_operation_id,
            installation_revision,binding_revision,actor,authority_data,content_hash,retirement_kind,runtime_disable_operation_id,runtime_enable_operation_id)
          VALUES(v_org,v_project,v_receipt_id,p_installation_id,v_binding.generation,NULL,NULL,
            p_expected_installation_revision,v_binding.revision+1,BTRIM(p_actor),v_authority,v_hash,'enabled_undispatched',v_lifecycle.disable_operation_id,v_enable.operation_id);
          UPDATE public.extension_runtime_binding SET desired_state='uninstalled',observed_state='stopped',
            enabled=false,operation_fence=true,revision=revision+1
            WHERE org_id=v_org AND project_id=v_project AND installation_id=p_installation_id
              AND generation=v_binding.generation AND revision=v_binding.revision
              AND desired_state='disabled' AND observed_state='unknown' AND NOT enabled AND operation_fence;
          IF NOT FOUND THEN RAISE EXCEPTION 'configured unactivated binding CAS drifted' USING ERRCODE='40001'; END IF;
          RETURN QUERY SELECT true,jsonb_build_object('receiptId',v_receipt_id::text,'authorityData',v_authority),v_hash;
          RETURN;
        END IF;
"""


def upgrade():
    conn=op.get_bind()
    source=conn.execute(sa.text("SELECT pg_get_functiondef('extension_runtime_uninstall_commit_ar2_018(uuid,bigint,text)'::regprocedure)")).scalar_one()
    anchor='SELECT count(*) INTO v_lifecycle_count'
    declaration='v_installation record;v_binding record;v_lifecycle record;'
    if source.count(anchor)!=1 or source.count(declaration)!=1 or "'configured_unactivated'" not in source or "'enabled_undispatched'" in source:
        raise RuntimeError('exact a0v_020 uninstall authority required')
    previous=conn.execute(sa.text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='extension_runtime_uninstall_receipt'::regclass AND conname='retirement_kind_authority'")).scalar_one()
    if not previous.startswith('CHECK ('):raise RuntimeError('exact retirement constraint required')
    op.execute("""ALTER TABLE extension_runtime_uninstall_receipt
        ADD COLUMN runtime_enable_operation_id uuid,
        ADD COLUMN runtime_disable_operation_id uuid,
        ADD FOREIGN KEY(org_id,project_id,runtime_enable_operation_id) REFERENCES extension_runtime_operation(org_id,project_id,operation_id),
        ADD FOREIGN KEY(org_id,project_id,runtime_disable_operation_id) REFERENCES extension_runtime_operation(org_id,project_id,operation_id),
        DROP CONSTRAINT retirement_kind_authority""")
    op.execute("ALTER TABLE extension_runtime_uninstall_receipt ADD CONSTRAINT retirement_kind_authority CHECK ("
        "(runtime_enable_operation_id IS NULL AND runtime_disable_operation_id IS NULL AND "+previous[6:]+") OR "
        "(retirement_kind='enabled_undispatched' AND unactivated_disable_operation_id IS NULL "
        "AND disable_operation_id IS NULL AND activation_operation_id IS NULL "
        "AND runtime_enable_operation_id IS NOT NULL AND runtime_disable_operation_id IS NOT NULL "
        "AND (authority_data->>'retirementKind') IS NOT DISTINCT FROM 'enabled_undispatched' "
        "AND (authority_data->>'enableOperationId') IS NOT DISTINCT FROM runtime_enable_operation_id::text "
        "AND (authority_data->>'disableOperationId') IS NOT DISTINCT FROM runtime_disable_operation_id::text))")
    op.execute(source.replace(declaration,declaration+'v_enable record;').replace(anchor,BRANCH+anchor))


def downgrade():
    raise RuntimeError('Forward-only enabled undispatched retirement authority')
