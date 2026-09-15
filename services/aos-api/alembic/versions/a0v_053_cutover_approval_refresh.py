"""Add immutable approval refresh authority for an in-flight cutover."""

from alembic import op


revision = "a0v_053"
down_revision = "a0v_052"
branch_labels = depends_on = None


FUNCTION = "public.extension_dispatch_cutover_commit_ar2_014(uuid,text)"
OLD = "v_operation.approval_ref"
NEW = "public.extension_dispatch_cutover_effective_approval_ref_a0v_053(p_cutover_operation_id)"


def _replace_commit_reference(expected: str, replacement: str, *, upgrading: bool) -> None:
    guard = (
        f"IF strpos(v_definition, '{NEW}') > 0 THEN RETURN; END IF;"
        if upgrading
        else f"IF strpos(v_definition, '{NEW}') = 0 THEN RETURN; END IF;"
    )
    op.execute(
        f"""DO $migration$
        DECLARE v_definition text;
        BEGIN
          SELECT pg_get_functiondef(to_regprocedure('{FUNCTION}')) INTO v_definition;
          IF v_definition IS NULL THEN
            RAISE EXCEPTION 'cutover commit function is unavailable';
          END IF;
          {guard}
          IF strpos(v_definition, '{expected}') = 0 THEN
            RAISE EXCEPTION 'cutover approval reference predicate drifted';
          END IF;
          EXECUTE replace(v_definition, '{expected}', '{replacement}');
        END $migration$"""
    )


def upgrade() -> None:
    op.execute("""CREATE TABLE extension_dispatch_cutover_approval_refresh_receipt(
      org_id text NOT NULL,
      project_id text NOT NULL,
      receipt_id uuid NOT NULL,
      cutover_operation_id uuid NOT NULL,
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 240),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      prepare_receipt_ref jsonb NOT NULL CHECK(jsonb_typeof(prepare_receipt_ref)='object'),
      old_approval_ref jsonb NOT NULL CHECK(jsonb_typeof(old_approval_ref)='object'),
      new_approval_ref jsonb NOT NULL CHECK(jsonb_typeof(new_approval_ref)='object'),
      authority_data jsonb NOT NULL CHECK(jsonb_typeof(authority_data)='object'),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      refreshed_by text NOT NULL CHECK(length(refreshed_by) BETWEEN 1 AND 240),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,cutover_operation_id),
      UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,cutover_operation_id)
        REFERENCES extension_dispatch_cutover_operation(org_id,project_id,cutover_operation_id)
    )""")
    op.execute("ALTER TABLE extension_dispatch_cutover_approval_refresh_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE extension_dispatch_cutover_approval_refresh_receipt FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope ON extension_dispatch_cutover_approval_refresh_receipt
      TO aos_extension_maintainer
      USING(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true))""")
    op.execute("REVOKE ALL ON extension_dispatch_cutover_approval_refresh_receipt FROM PUBLIC,aos_runtime")
    op.execute("GRANT SELECT,INSERT ON extension_dispatch_cutover_approval_refresh_receipt TO aos_extension_maintainer")
    op.execute("""CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE
      ON extension_dispatch_cutover_approval_refresh_receipt FOR EACH ROW
      EXECUTE FUNCTION extension_reject_history_mutation()""")
    op.execute("""CREATE FUNCTION extension_dispatch_cutover_effective_approval_ref_a0v_053(
      p_cutover_operation_id uuid) RETURNS jsonb
      LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_ref jsonb;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL
          OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged cutover maintainer is required'
          USING ERRCODE='42501'; END IF;
        SELECT COALESCE(r.new_approval_ref,o.approval_ref) INTO v_ref
          FROM public.extension_dispatch_cutover_operation o
          LEFT JOIN public.extension_dispatch_cutover_approval_refresh_receipt r
            USING(org_id,project_id,cutover_operation_id)
         WHERE o.org_id=v_org AND o.project_id=v_project
           AND o.cutover_operation_id=p_cutover_operation_id;
        IF v_ref IS NULL THEN RAISE EXCEPTION 'cutover approval is unavailable'
          USING ERRCODE='55000'; END IF;
        RETURN v_ref;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION extension_dispatch_cutover_effective_approval_ref_a0v_053(uuid) FROM PUBLIC,aos_runtime")
    op.execute("GRANT EXECUTE ON FUNCTION extension_dispatch_cutover_effective_approval_ref_a0v_053(uuid) TO aos_extension_maintainer")
    _replace_commit_reference(OLD, NEW, upgrading=True)


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM extension_dispatch_cutover_approval_refresh_receipt LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade a0v_053 with approval refresh authority'
        USING ERRCODE='55000'; END IF;
    END $$""")
    _replace_commit_reference(NEW, OLD, upgrading=False)
    op.execute("DROP FUNCTION extension_dispatch_cutover_effective_approval_ref_a0v_053(uuid)")
    op.execute("DROP TABLE extension_dispatch_cutover_approval_refresh_receipt")
