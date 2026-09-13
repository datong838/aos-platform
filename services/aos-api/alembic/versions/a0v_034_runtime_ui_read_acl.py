"""Seal UI read ACLs against inherited public-schema default privileges."""
from alembic import op

revision='a0v_034'
down_revision='a0v_033'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    REVOKE ALL ON public.extension_runtime_ui_read_request
      FROM PUBLIC,aos_runtime,aos_ui_read_api,aos_extension_maintainer;
    DO $$ DECLARE v_columns text;
    BEGIN
      SELECT string_agg(format('%I',attname),', ' ORDER BY attnum) INTO v_columns
        FROM pg_catalog.pg_attribute
        WHERE attrelid='public.extension_runtime_ui_read_request'::regclass AND attnum>0 AND NOT attisdropped;
      EXECUTE format('REVOKE SELECT (%1$s),INSERT (%1$s),UPDATE (%1$s),REFERENCES (%1$s)
        ON public.extension_runtime_ui_read_request FROM PUBLIC,aos_runtime,aos_ui_read_api,aos_extension_maintainer',v_columns);
    END $$;
    GRANT SELECT ON public.extension_runtime_ui_read_request TO aos_runtime;
    GRANT UPDATE(state,revision,claimed_at,completed_at,owner_token_hash,attempt_id,snapshot_hash,
        attempt_request_hash,result_json,result_hash,failure_code)
        ON public.extension_runtime_ui_read_request TO aos_runtime;
    ''')


def downgrade():
    raise RuntimeError('UI read least-privilege boundary must be retained')
