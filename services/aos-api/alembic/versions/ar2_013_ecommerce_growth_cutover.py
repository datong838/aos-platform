"""Persistent ecommerce growth group-cutover preparation authority."""

from alembic import op


revision = "ar2_013"
down_revision = "ar2_012"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE extension_dispatch_cutover_operation (
      org_id text NOT NULL,
      project_id text NOT NULL,
      cutover_operation_id uuid NOT NULL,
      kind text NOT NULL CHECK(kind IN ('activate','rollback')),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 240),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      status text NOT NULL CHECK(status IN (
        'prepared','committing','committed','fencing','draining','rolled_back','needs_attention')),
      cutover_group_id uuid NOT NULL,
      expected_group_revision bigint NOT NULL CHECK(expected_group_revision > 0),
      target_group_revision bigint NOT NULL CHECK(target_group_revision = expected_group_revision + 1),
      target_installation_id uuid NOT NULL,
      target_generation uuid NOT NULL,
      target_execution_epoch bigint NOT NULL CHECK(target_execution_epoch > 0),
      target_runtime_revision bigint NOT NULL CHECK(target_runtime_revision > 0),
      operation_ids jsonb NOT NULL CHECK(jsonb_typeof(operation_ids)='array'),
      old_dispatch_snapshot jsonb NOT NULL CHECK(jsonb_typeof(old_dispatch_snapshot)='array'),
      new_dispatch_snapshot jsonb NOT NULL CHECK(jsonb_typeof(new_dispatch_snapshot)='array'),
      checkpoint jsonb NOT NULL CHECK(jsonb_typeof(checkpoint)='object'),
      occurrence_watermark timestamptz,
      pending_target_receipt_refs jsonb NOT NULL CHECK(jsonb_typeof(pending_target_receipt_refs)='array'),
      policy_ref jsonb NOT NULL CHECK(jsonb_typeof(policy_ref)='object'),
      approval_ref jsonb NOT NULL CHECK(jsonb_typeof(approval_ref)='object'),
      requested_by text NOT NULL CHECK(length(requested_by) BETWEEN 1 AND 240),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,cutover_operation_id),
      UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,target_installation_id,target_generation)
        REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation)
    );
    CREATE INDEX extension_dispatch_cutover_group_operation
      ON extension_dispatch_cutover_operation(
        org_id,project_id,cutover_group_id,status,cutover_operation_id);

    CREATE TABLE extension_dispatch_cutover_event (
      org_id text NOT NULL,
      project_id text NOT NULL,
      cutover_operation_id uuid NOT NULL,
      sequence bigint NOT NULL CHECK(sequence > 0),
      event_id uuid NOT NULL,
      event_type text NOT NULL CHECK(event_type IN (
        'CUTOVER_PREPARED','CUTOVER_COMMITTED','CUTOVER_FENCED',
        'CUTOVER_DRAINED','CUTOVER_ROLLED_BACK','CUTOVER_NEEDS_ATTENTION')),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      payload_hash text NOT NULL CHECK(payload_hash ~ '^sha256:[0-9a-f]{64}$'),
      occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,cutover_operation_id,sequence),
      UNIQUE(org_id,project_id,event_id),
      FOREIGN KEY(org_id,project_id,cutover_operation_id)
        REFERENCES extension_dispatch_cutover_operation(org_id,project_id,cutover_operation_id)
    );

    CREATE TABLE extension_dispatch_cutover_receipt (
      org_id text NOT NULL,
      project_id text NOT NULL,
      receipt_id uuid NOT NULL,
      cutover_operation_id uuid NOT NULL,
      phase text NOT NULL CHECK(phase IN ('prepare','commit','fence','drain','rollback')),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      authority_data jsonb NOT NULL CHECK(jsonb_typeof(authority_data)='object'),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,cutover_operation_id,phase),
      FOREIGN KEY(org_id,project_id,cutover_operation_id)
        REFERENCES extension_dispatch_cutover_operation(org_id,project_id,cutover_operation_id)
    );
    """)
    for table in (
        "extension_dispatch_cutover_operation",
        "extension_dispatch_cutover_event",
        "extension_dispatch_cutover_receipt",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope ON {table} TO aos_extension_maintainer
              USING(org_id=current_setting('aos.org_id',true)
                AND project_id=current_setting('aos.project_id',true))
              WITH CHECK(org_id=current_setting('aos.org_id',true)
                AND project_id=current_setting('aos.project_id',true))"""
        )
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
    op.execute("REVOKE ALL ON extension_dispatch_cutover_operation FROM aos_runtime")
    op.execute("REVOKE ALL ON extension_dispatch_cutover_event FROM aos_runtime")
    op.execute("REVOKE ALL ON extension_dispatch_cutover_receipt FROM aos_runtime")
    op.execute("GRANT SELECT,INSERT ON extension_dispatch_cutover_operation TO aos_extension_maintainer")
    op.execute("GRANT UPDATE(status,updated_at) ON extension_dispatch_cutover_operation TO aos_extension_maintainer")
    op.execute("GRANT SELECT,INSERT ON extension_dispatch_cutover_event TO aos_extension_maintainer")
    op.execute("GRANT SELECT,INSERT ON extension_dispatch_cutover_receipt TO aos_extension_maintainer")
    op.execute("GRANT SELECT ON extension_operation_dispatch_binding,extension_runtime_binding TO aos_extension_maintainer")
    op.execute("GRANT SELECT ON aip_action_proposal,aip_action_draft,aip_action_approval_event TO aos_extension_maintainer")
    op.execute("""CREATE FUNCTION extension_dispatch_cutover_lock_approval_ar2_013(
      p_approval_event_id text) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_proposal_id text;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL
          OR length(BTRIM(p_approval_event_id)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged cutover maintainer is required'
          USING ERRCODE='42501'; END IF;
        SELECT a.proposal_id INTO v_proposal_id
          FROM public.aip_action_approval_event a
          WHERE a.org_id=v_org AND a.project_id=v_project
            AND a.approval_event_id=p_approval_event_id;
        IF v_proposal_id IS NULL THEN
          RAISE EXCEPTION 'cutover approval is unavailable' USING ERRCODE='P0002';
        END IF;
        PERFORM 1 FROM public.aip_action_proposal p
          WHERE p.org_id=v_org AND p.project_id=v_project AND p.proposal_id=v_proposal_id
          FOR SHARE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'cutover proposal is unavailable' USING ERRCODE='P0002';
        END IF;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION extension_dispatch_cutover_lock_approval_ar2_013(text) FROM PUBLIC,aos_runtime")
    op.execute("GRANT EXECUTE ON FUNCTION extension_dispatch_cutover_lock_approval_ar2_013(text) TO aos_extension_maintainer")
    op.execute("""CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE
      ON extension_dispatch_cutover_event FOR EACH ROW
      EXECUTE FUNCTION extension_reject_history_mutation()""")
    op.execute("""CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE
      ON extension_dispatch_cutover_receipt FOR EACH ROW
      EXECUTE FUNCTION extension_reject_history_mutation()""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM extension_dispatch_cutover_operation LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade ar2_013 with cutover authority'
        USING ERRCODE='55000'; END IF;
    END $$""")
    op.execute("DROP FUNCTION extension_dispatch_cutover_lock_approval_ar2_013(text)")
    op.execute("DROP TABLE extension_dispatch_cutover_receipt")
    op.execute("DROP TABLE extension_dispatch_cutover_event")
    op.execute("DROP TABLE extension_dispatch_cutover_operation")
