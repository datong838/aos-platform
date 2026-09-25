"""Add an empty immutable canonical witness sidecar; no writer is granted."""

from alembic import op


revision = "a0v_097"
down_revision = "a0v_096"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE public.pipeline_snapshot_group_canonical_witness_a0v_097 (
      org_id text NOT NULL, project_id text NOT NULL, group_id uuid NOT NULL,
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      manifest_hash text NOT NULL CHECK(manifest_hash ~ '^sha256:[0-9a-f]{64}$'),
      binding_canonical_json text NOT NULL,
      manifest_canonical_json text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,group_id),
      FOREIGN KEY(org_id,project_id,group_id,request_hash)
        REFERENCES public.pipeline_snapshot_group_claim(org_id,project_id,group_id,request_hash),
      FOREIGN KEY(org_id,project_id,group_id)
        REFERENCES public.pipeline_snapshot_group_input(org_id,project_id,group_id),
      CHECK(octet_length(binding_canonical_json)<=65536
        AND octet_length(manifest_canonical_json)<=65536),
      CHECK(jsonb_typeof(binding_canonical_json::jsonb)='object'
        AND jsonb_typeof(manifest_canonical_json::jsonb)='object'),
      CHECK('sha256:'||encode(sha256(convert_to(binding_canonical_json,'UTF8')),'hex')=request_hash
        AND 'sha256:'||encode(sha256(convert_to(manifest_canonical_json,'UTF8')),'hex')=manifest_hash)
    );
    ALTER TABLE public.pipeline_snapshot_group_canonical_witness_a0v_097
      ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.pipeline_snapshot_group_canonical_witness_a0v_097
      FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON public.pipeline_snapshot_group_canonical_witness_a0v_097
      USING(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true));
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON
      public.pipeline_snapshot_group_canonical_witness_a0v_097
      FOR EACH ROW EXECUTE FUNCTION public.extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON
      public.pipeline_snapshot_group_canonical_witness_a0v_097
      FOR EACH STATEMENT EXECUTE FUNCTION public.extension_reject_history_mutation();
    REVOKE ALL ON public.pipeline_snapshot_group_canonical_witness_a0v_097
      FROM PUBLIC,aos_runtime,aos_extension_directory,aos_extension_maintainer;
    """)


def downgrade() -> None:
    raise RuntimeError("canonical witness sidecar must not be discarded by downgrade")
