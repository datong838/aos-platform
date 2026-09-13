"""Bounded tenant dispatch row locks without direct runtime DML privileges."""
from alembic import op

revision = 'a0v_028'
down_revision = 'a0v_027'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r'''
    CREATE FUNCTION public.extension_dispatch_lock_group_a0v_028(p_group_id uuid)
    RETURNS TABLE(operation_id text,handler_kind text,installation_id uuid,generation uuid,
        execution_epoch bigint,operation_fence boolean,revision bigint,cutover_group_id uuid,
        cutover_group_revision bigint)
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
        v_project text:=nullif(current_setting('aos.project_id',true),'');v_count bigint;
    BEGIN
        IF v_org IS NULL OR v_project IS NULL OR p_group_id IS NULL
            OR current_setting('role') IS DISTINCT FROM 'aos_runtime'
            OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
            OR NOT pg_has_role(session_user,'aos_runtime','MEMBER')
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'scoped runtime dispatch lock required' USING ERRCODE='42501'; END IF;
        RETURN QUERY SELECT d.operation_id,d.handler_kind,d.installation_id,d.generation,
            d.execution_epoch,d.operation_fence,d.revision,d.cutover_group_id,d.cutover_group_revision
            FROM public.extension_operation_dispatch_binding d
            WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=p_group_id
            ORDER BY d.operation_id,d.installation_id,d.generation LIMIT 10 FOR UPDATE;
        GET DIAGNOSTICS v_count=ROW_COUNT;
        IF v_count<>9 OR EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding d
            WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=p_group_id
              AND d.operation_id NOT IN (
                'ecommerce_growth_investigation_describe','ecommerce_growth_case_put',
                'ecommerce_growth_schedule_put','ecommerce_growth_schedule_trigger',
                'ecommerce_growth_data_fulfill','ecommerce_growth_analysis_advance',
                'ecommerce_growth_review_advance','ecommerce_growth_content_generate',
                'ecommerce_growth_content_review'))
        THEN RAISE EXCEPTION 'complete ecommerce dispatch group required' USING ERRCODE='23514'; END IF;
    END $$;
    REVOKE ALL ON FUNCTION public.extension_dispatch_lock_group_a0v_028(uuid)
        FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION public.extension_dispatch_lock_group_a0v_028(uuid) TO aos_runtime;
    REVOKE ALL ON public.extension_operation_dispatch_binding FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    DO $$ DECLARE v_columns text;
    BEGIN
        SELECT string_agg(format('%I',attname),', ' ORDER BY attnum) INTO v_columns
            FROM pg_catalog.pg_attribute
            WHERE attrelid='public.extension_operation_dispatch_binding'::regclass AND attnum>0 AND NOT attisdropped;
        EXECUTE format('REVOKE SELECT (%1$s),INSERT (%1$s),UPDATE (%1$s),REFERENCES (%1$s)
            ON public.extension_operation_dispatch_binding FROM PUBLIC,aos_runtime,aos_extension_maintainer',v_columns);
    END $$;
    GRANT SELECT ON public.extension_operation_dispatch_binding TO aos_runtime,aos_extension_maintainer;
    ''')


def downgrade():
    raise RuntimeError('dispatch authority and restricted row-lock boundary must be retained')
