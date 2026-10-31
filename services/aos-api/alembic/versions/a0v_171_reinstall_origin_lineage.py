"""Add immutable tenant-scoped lineage for an original reinstall command."""
from alembic import op


revision = "a0v_171"
down_revision = "a0v_170"
branch_labels = depends_on = None


TABLE = "public.bundle_installation_reinstall_origin"
SCOPE = (
    "org_id = current_setting('aos.org_id', true) AND "
    "project_id = current_setting('aos.project_id', true)"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {TABLE} (
          org_id TEXT NOT NULL CHECK (
            org_id = btrim(org_id) AND char_length(org_id) BETWEEN 1 AND 160
          ),
          project_id TEXT NOT NULL CHECK (
            project_id = btrim(project_id)
            AND char_length(project_id) BETWEEN 1 AND 160
          ),
          target_installation_pk UUID NOT NULL,
          target_revision BIGINT NOT NULL CHECK (target_revision = 1),
          source_installation_pk UUID NOT NULL,
          source_terminal_revision BIGINT NOT NULL
            CHECK (source_terminal_revision >= 1),
          source_lock_hash TEXT NOT NULL
            CHECK (source_lock_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          target_lock_hash TEXT NOT NULL
            CHECK (target_lock_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          actor TEXT NOT NULL CHECK (
            actor = btrim(actor) AND char_length(actor) BETWEEN 1 AND 240
          ),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, target_installation_pk, target_revision),
          CONSTRAINT fk_reinstall_origin_workspace_a0v171
            FOREIGN KEY (org_id, project_id)
            REFERENCES public.meta_workspace(org_id, project_id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_reinstall_origin_target_revision_a0v171
            FOREIGN KEY (
              org_id, project_id, target_installation_pk, target_revision
            )
            REFERENCES public.bundle_installation_revision(
              org_id, project_id, installation_pk, revision
            )
            ON DELETE RESTRICT,
          CONSTRAINT fk_reinstall_origin_source_revision_a0v171
            FOREIGN KEY (
              org_id, project_id,
              source_installation_pk, source_terminal_revision
            )
            REFERENCES public.bundle_installation_revision(
              org_id, project_id, installation_pk, revision
            )
            ON DELETE RESTRICT,
          CHECK (target_installation_pk <> source_installation_pk)
        )
        """
    )
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_scope_bundle_installation_reinstall_origin_a0v171
          ON {TABLE} FOR ALL TO aos_runtime
          USING ({SCOPE}) WITH CHECK ({SCOPE})
        """
    )
    op.execute(f"REVOKE ALL ON {TABLE} FROM PUBLIC, aos_runtime")
    op.execute(f"GRANT SELECT, INSERT ON {TABLE} TO aos_runtime")
    op.execute(
        f"""
        CREATE TRIGGER trg_bundle_installation_reinstall_origin_immutable
          BEFORE UPDATE OR DELETE ON {TABLE}
          FOR EACH ROW
          EXECUTE FUNCTION public.guard_bundle_control_immutable()
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_bundle_installation_reinstall_origin_truncate_guard
          BEFORE TRUNCATE ON {TABLE}
          FOR EACH STATEMENT
          EXECUTE FUNCTION public.guard_bundle_control_immutable()
        """
    )


def downgrade() -> None:
    raise RuntimeError("immutable reinstall origin removal requires explicit reconciliation")
