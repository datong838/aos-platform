"""Fail-closed terminal TaskRun gate for the daily review target."""

from alembic import op


revision = "a0v_100"
down_revision = "a0v_099"
branch_labels = depends_on = None


_SIGNATURE = "TEXT,TEXT,UUID,BIGINT,JSONB,JSONB,JSONB,JSONB,JSONB"


def upgrade() -> None:
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION public.ecommerce_growth_daily_review_put_a0v_099({_SIGNATURE}) FROM aos_runtime"
    )
    op.execute(
        """CREATE FUNCTION public.ecommerce_growth_daily_review_put_a0v_100(
          p_command_id TEXT,p_target_id TEXT,p_lease_token UUID,p_checkpoint_version BIGINT,
          p_payload JSONB,p_review_ref JSONB,p_artifact_ref JSONB,p_task_ref JSONB,p_brief_ref JSONB
        ) RETURNS TABLE(receipt_ref JSONB,replayed BOOLEAN)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
          v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
          v_receipt JSONB;v_replayed BOOLEAN;v_terminal TEXT;
        BEGIN
          -- The old owner locks dispatch, runtime and feedback in that order.
          -- A terminal failure raises in this same transaction, undoing its insert.
          SELECT result.receipt_ref,result.replayed INTO v_receipt,v_replayed
            FROM public.ecommerce_growth_daily_review_put_a0v_099(
              p_command_id,p_target_id,p_lease_token,p_checkpoint_version,p_payload,
              p_review_ref,p_artifact_ref,p_task_ref,p_brief_ref) AS result;
          IF v_receipt IS NULL OR coalesce(v_org,'')='' OR coalesce(v_project,'')=''
          THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='daily review target is unproven'; END IF;
          SELECT a.artifact_id INTO v_terminal FROM public.aip_artifact a
            JOIN public.aip_task_run r ON r.org_id=a.org_id AND r.project_id=a.project_id
              AND r.run_id=a.run_id AND r.task_id=p_task_ref->>'resourceId'
              AND r.status='succeeded'
            JOIN public.aip_task t ON t.org_id=r.org_id AND t.project_id=r.project_id
              AND t.task_id=r.task_id AND t.status='completed'
           WHERE a.org_id=v_org AND a.project_id=v_project
             AND a.artifact_id=p_artifact_ref->>'resourceId'
             AND a.artifact_type='ecommerce_content'
             AND p_artifact_ref->>'contentHash'='sha256:'||a.content_hash
             AND p_artifact_ref->'revision'=to_jsonb(coalesce(a.family_revision,1));
          IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='daily review terminal TaskRun unavailable'; END IF;
          RETURN QUERY SELECT v_receipt,v_replayed;
        END $$"""
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION public.ecommerce_growth_daily_review_put_a0v_100({_SIGNATURE}) FROM PUBLIC"
    )
    op.execute(
        f"GRANT EXECUTE ON FUNCTION public.ecommerce_growth_daily_review_put_a0v_100({_SIGNATURE}) TO aos_runtime"
    )


def downgrade() -> None:
    raise RuntimeError("terminal feedback gate must not be removed")
