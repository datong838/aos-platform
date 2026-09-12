"""Retire verified but never configured/enabled instances with honest receipts."""
from alembic import op
import sqlalchemy as sa

revision = "a0v_019"
down_revision = "a0v_018"
branch_labels = depends_on = None

BRANCH = """
        IF v_binding.config_ref IS NULL
          AND NOT EXISTS (SELECT 1 FROM public.extension_runtime_configuration c
            WHERE c.org_id=v_org AND c.project_id=v_project AND c.installation_id=p_installation_id)
          AND NOT EXISTS (SELECT 1 FROM public.extension_runtime_operation o
            WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=p_installation_id
              AND (o.kind IN ('enable','disable','configure') OR o.status NOT IN ('succeeded','failed','cancelled')))
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
            RAISE EXCEPTION 'never-enabled runtime resources are not confirmed released' USING ERRCODE='55000';
          END IF;
          v_authority:=jsonb_build_object('orgId',v_org,'projectId',v_project,
            'installationId',p_installation_id::text,'generation',v_binding.generation::text,
            'installationRevision',p_expected_installation_revision,'bindingRevision',v_binding.revision+1,
            'retirementKind','never_enabled','releasedResourceCount',v_resource_count,
            'configurationCount',0,'enableCount',0,'dispatchCount',0,'businessExecutionCount',0,
            'actor',BTRIM(p_actor));
          v_hash:='sha256:'||encode(sha256(convert_to(v_authority::text,'UTF8')),'hex');
          INSERT INTO public.extension_runtime_uninstall_receipt(
            org_id,project_id,receipt_id,installation_id,generation,disable_operation_id,activation_operation_id,
            installation_revision,binding_revision,actor,authority_data,content_hash,retirement_kind)
          VALUES(v_org,v_project,v_receipt_id,p_installation_id,v_binding.generation,NULL,NULL,
            p_expected_installation_revision,v_binding.revision+1,BTRIM(p_actor),v_authority,v_hash,'never_enabled');
          UPDATE public.extension_runtime_binding SET desired_state='uninstalled',observed_state='stopped',
            enabled=false,operation_fence=true,revision=revision+1
            WHERE org_id=v_org AND project_id=v_project AND installation_id=p_installation_id
              AND generation=v_binding.generation AND revision=v_binding.revision
              AND desired_state='disabled' AND observed_state='unknown' AND NOT enabled AND operation_fence;
          IF NOT FOUND THEN RAISE EXCEPTION 'never-enabled binding CAS drifted' USING ERRCODE='40001'; END IF;
          RETURN QUERY SELECT true,jsonb_build_object('receiptId',v_receipt_id::text,'authorityData',v_authority),v_hash;
          RETURN;
        END IF;
"""


def upgrade():
    op.execute("""ALTER TABLE extension_runtime_uninstall_receipt
      ADD COLUMN retirement_kind text NOT NULL DEFAULT 'detached',
      ALTER COLUMN disable_operation_id DROP NOT NULL,
      ALTER COLUMN activation_operation_id DROP NOT NULL,
      ADD CONSTRAINT retirement_kind_authority CHECK (
        (retirement_kind='detached' AND disable_operation_id IS NOT NULL AND activation_operation_id IS NOT NULL)
        OR (retirement_kind='never_enabled' AND disable_operation_id IS NULL AND activation_operation_id IS NULL
            AND (authority_data->>'retirementKind') IS NOT DISTINCT FROM 'never_enabled'))""")
    source = op.get_bind().execute(sa.text("SELECT pg_get_functiondef('extension_runtime_uninstall_commit_ar2_018(uuid,bigint,text)'::regprocedure)")).scalar_one()
    anchor = "SELECT count(*) INTO v_lifecycle_count"
    if source.count(anchor) != 1:
        raise RuntimeError('uninstall authority baseline differs')
    op.execute(source.replace(anchor, BRANCH + anchor))


def downgrade():
    raise RuntimeError('Forward-only never-enabled retirement history')
