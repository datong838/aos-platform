"""TI-2 E1 nullable Module instance and overlay expansion.

Revision ID: 228ti2e1expand
Revises: 228ti1e3exec
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti2e1expand"
down_revision: str | Sequence[str] | None = "228ti1e3exec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHILDREN = (
    "module_canvas_config",
    "module_deployment",
    "module_events",
    "module_interface",
    "module_query",
    "module_variable",
    "module_widget_instance",
)

_HISTORY_TABLES = (
    "module_organization_profile",
    "module_instance_overlay",
    "module_user_view_preference",
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE meta_module
          ADD COLUMN module_pk UUID,
          ADD COLUMN module_id TEXT,
          ADD COLUMN template_id TEXT,
          ADD COLUMN template_version TEXT,
          ADD COLUMN installation_id UUID,
          ADD COLUMN active_overlay_revision BIGINT,
          ADD COLUMN effective_config_hash TEXT,
          ADD COLUMN deleted_at TIMESTAMPTZ
        """
    )
    op.execute(
        "ALTER TABLE meta_module ADD CONSTRAINT uq_meta_module_scope_pk_ti2 "
        "UNIQUE (org_id, project_id, module_pk)"
    )
    op.execute(
        "ALTER TABLE meta_module ADD CONSTRAINT uq_meta_module_scope_id_ti2 "
        "UNIQUE (org_id, project_id, module_id)"
    )
    op.execute(
        "ALTER TABLE meta_module ADD CONSTRAINT fk_meta_module_installation_ti2 "
        "FOREIGN KEY (org_id, project_id, installation_id) "
        "REFERENCES bundle_installation (org_id, project_id, installation_pk) NOT VALID"
    )

    for table in _CHILDREN:
        op.execute(f"ALTER TABLE {table} ADD COLUMN module_pk UUID")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_module_ti2 "
            "FOREIGN KEY (org_id, project_id, module_pk) "
            "REFERENCES meta_module (org_id, project_id, module_pk) NOT VALID"
        )

    op.execute(
        """
        CREATE TABLE module_organization_profile (
          org_id TEXT NOT NULL,
          profile_revision BIGINT NOT NULL,
          profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          profile_hash TEXT NOT NULL CHECK (profile_hash ~ '^[0-9a-f]{64}$'),
          actor_hash TEXT NOT NULL CHECK (actor_hash ~ '^[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, profile_revision),
          FOREIGN KEY (org_id) REFERENCES meta_org (id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE module_instance_overlay (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          module_pk UUID NOT NULL,
          overlay_revision BIGINT NOT NULL,
          base_template_id TEXT NOT NULL,
          base_template_version TEXT NOT NULL,
          base_content_hash TEXT NOT NULL CHECK (base_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          patch_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          effective_config_hash TEXT NOT NULL CHECK (effective_config_hash ~ '^sha256:[0-9a-f]{64}$'),
          actor_hash TEXT NOT NULL CHECK (actor_hash ~ '^[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, module_pk, overlay_revision)
        )
        """
    )
    op.execute(
        "ALTER TABLE module_instance_overlay "
        "ADD CONSTRAINT fk_module_instance_overlay_module_ti2 "
        "FOREIGN KEY (org_id, project_id, module_pk) "
        "REFERENCES meta_module (org_id, project_id, module_pk) NOT VALID"
    )
    op.execute(
        "ALTER TABLE meta_module ADD CONSTRAINT fk_meta_module_active_overlay_ti2 "
        "FOREIGN KEY (org_id, project_id, module_pk, active_overlay_revision) "
        "REFERENCES module_instance_overlay "
        "(org_id, project_id, module_pk, overlay_revision) NOT VALID"
    )
    op.execute(
        """
        CREATE TABLE module_user_view_preference (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          module_pk UUID NOT NULL,
          subject TEXT NOT NULL,
          preference_key TEXT NOT NULL,
          revision BIGINT NOT NULL,
          preference_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          preference_hash TEXT NOT NULL CHECK (preference_hash ~ '^[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (
            org_id, project_id, module_pk, subject, preference_key, revision
          )
        )
        """
    )
    op.execute(
        "ALTER TABLE module_user_view_preference "
        "ADD CONSTRAINT fk_module_user_view_preference_module_ti2 "
        "FOREIGN KEY (org_id, project_id, module_pk) "
        "REFERENCES meta_module (org_id, project_id, module_pk) NOT VALID"
    )
    op.execute(
        """
        CREATE FUNCTION guard_module_ti2_history_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'TI-2 module revision history is append-only'
            USING ERRCODE = '23514';
        END;
        $$
        """
    )
    for table in _HISTORY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable "
            f"BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW "
            "EXECUTE FUNCTION guard_module_ti2_history_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_truncate_guard "
            f"BEFORE TRUNCATE ON {table} FOR EACH STATEMENT "
            "EXECUTE FUNCTION guard_module_ti2_history_immutable()"
        )


def downgrade() -> None:
    checks = [
        f"EXISTS (SELECT 1 FROM {table} LIMIT 1)" for table in _HISTORY_TABLES
    ]
    checks.extend(
        [
            "EXISTS (SELECT 1 FROM meta_module WHERE module_pk IS NOT NULL "
            "OR module_id IS NOT NULL OR template_id IS NOT NULL "
            "OR template_version IS NOT NULL OR installation_id IS NOT NULL "
            "OR active_overlay_revision IS NOT NULL "
            "OR effective_config_hash IS NOT NULL OR deleted_at IS NOT NULL LIMIT 1)",
            *(
                f"EXISTS (SELECT 1 FROM {table} WHERE module_pk IS NOT NULL LIMIT 1)"
                for table in _CHILDREN
            ),
        ]
    )
    op.execute(
        "DO $$ BEGIN IF "
        + " OR ".join(checks)
        + " THEN RAISE EXCEPTION 'archive TI-2 module expand data before downgrade'; "
        "END IF; END; $$"
    )
    op.execute(
        "ALTER TABLE meta_module DROP CONSTRAINT fk_meta_module_active_overlay_ti2"
    )
    for table in reversed(_HISTORY_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION guard_module_ti2_history_immutable()")
    for table in reversed(_CHILDREN):
        op.execute(f"ALTER TABLE {table} DROP COLUMN module_pk")
    op.execute("ALTER TABLE meta_module DROP CONSTRAINT fk_meta_module_installation_ti2")
    op.execute("ALTER TABLE meta_module DROP CONSTRAINT uq_meta_module_scope_id_ti2")
    op.execute("ALTER TABLE meta_module DROP CONSTRAINT uq_meta_module_scope_pk_ti2")
    op.execute(
        "ALTER TABLE meta_module "
        "DROP COLUMN module_pk, DROP COLUMN module_id, DROP COLUMN template_id, "
        "DROP COLUMN template_version, DROP COLUMN installation_id, "
        "DROP COLUMN active_overlay_revision, DROP COLUMN effective_config_hash, "
        "DROP COLUMN deleted_at"
    )
