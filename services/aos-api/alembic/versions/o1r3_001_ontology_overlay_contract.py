"""O1-R3: installation-bound organization ontology overlays.

Revision ID: o1r3_001
Revises: o1r2_001
Create Date: 2026-08-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1r3_001"
down_revision: str | Sequence[str] | None = "o1r2_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE ontology_overlay (
        org_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        installation_pk UUID NOT NULL,
        target_kind TEXT NOT NULL CHECK (target_kind IN ('ObjectType','LinkType')),
        target_id TEXT NOT NULL CHECK (BTRIM(target_id) <> ''),
        mode TEXT NOT NULL DEFAULT 'override' CHECK (mode IN ('override','inherit')),
        display_name TEXT,
        visible_properties JSONB,
        extended_properties JSONB,
        policies JSONB,
        base_schema_sha256 CHAR(64) NOT NULL
          CHECK (base_schema_sha256 ~ '^[0-9a-f]{64}$'),
        ontology_revision INTEGER NOT NULL CHECK (ontology_revision >= 1),
        is_active BOOLEAN NOT NULL DEFAULT FALSE,
        created_by TEXT NOT NULL CHECK (BTRIM(created_by) <> ''),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (
          org_id,workspace_id,installation_pk,target_kind,target_id,ontology_revision
        ),
        CONSTRAINT fk_ontology_overlay_installation
          FOREIGN KEY (org_id,workspace_id,installation_pk)
          REFERENCES bundle_installation(org_id,project_id,installation_pk)
          ON DELETE RESTRICT,
        CONSTRAINT fk_ontology_overlay_workspace
          FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT,
        CONSTRAINT ck_ontology_overlay_inherit_empty CHECK (
          mode='override' OR (
            display_name IS NULL AND visible_properties IS NULL
            AND COALESCE(extended_properties,'{}'::jsonb)='{}'::jsonb
            AND policies IS NULL
          )
        ),
        CHECK (updated_at >= created_at)
      );
      CREATE UNIQUE INDEX uq_ontology_overlay_active
        ON ontology_overlay(org_id,workspace_id,installation_pk,target_kind,target_id)
        WHERE is_active;
      CREATE INDEX idx_ontology_overlay_history
        ON ontology_overlay(org_id,workspace_id,installation_pk,target_kind,target_id,ontology_revision DESC);

      CREATE FUNCTION guard_ontology_overlay_history()
      RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF OLD.org_id IS DISTINCT FROM NEW.org_id
           OR OLD.workspace_id IS DISTINCT FROM NEW.workspace_id
           OR OLD.installation_pk IS DISTINCT FROM NEW.installation_pk
           OR OLD.target_kind IS DISTINCT FROM NEW.target_kind
           OR OLD.target_id IS DISTINCT FROM NEW.target_id
           OR OLD.ontology_revision IS DISTINCT FROM NEW.ontology_revision
           OR OLD.mode IS DISTINCT FROM NEW.mode
           OR OLD.display_name IS DISTINCT FROM NEW.display_name
           OR OLD.visible_properties IS DISTINCT FROM NEW.visible_properties
           OR OLD.extended_properties IS DISTINCT FROM NEW.extended_properties
           OR OLD.policies IS DISTINCT FROM NEW.policies
           OR OLD.base_schema_sha256 IS DISTINCT FROM NEW.base_schema_sha256
           OR OLD.created_by IS DISTINCT FROM NEW.created_by
           OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
          RAISE EXCEPTION 'ONTOLOGY_OVERLAY_HISTORY_IMMUTABLE' USING ERRCODE='55000';
        END IF;
        IF NOT OLD.is_active AND NEW.is_active THEN
          RAISE EXCEPTION 'ONTOLOGY_OVERLAY_REVISION_REACTIVATION_FORBIDDEN' USING ERRCODE='55000';
        END IF;
        IF NEW.updated_at < OLD.updated_at THEN
          RAISE EXCEPTION 'ONTOLOGY_OVERLAY_TIME_REGRESSION' USING ERRCODE='55000';
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER trg_guard_ontology_overlay_history
        BEFORE UPDATE ON ontology_overlay
        FOR EACH ROW EXECUTE FUNCTION guard_ontology_overlay_history();

      CREATE TABLE ontology_overlay_receipt (
        org_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL CHECK (BTRIM(idempotency_key) <> ''),
        request_hash CHAR(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
        installation_pk UUID NOT NULL,
        target_kind TEXT NOT NULL CHECK (target_kind IN ('ObjectType','LinkType')),
        target_id TEXT NOT NULL CHECK (BTRIM(target_id) <> ''),
        expected_ontology_revision INTEGER NOT NULL CHECK (expected_ontology_revision >= 0),
        resulting_ontology_revision INTEGER NOT NULL CHECK (resulting_ontology_revision >= 1),
        base_schema_sha256 CHAR(64) NOT NULL CHECK (base_schema_sha256 ~ '^[0-9a-f]{64}$'),
        actor TEXT NOT NULL CHECK (BTRIM(actor) <> ''),
        response_etag TEXT NOT NULL CHECK (BTRIM(response_etag) <> ''),
        result_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,idempotency_key),
        CONSTRAINT fk_ontology_overlay_receipt_installation
          FOREIGN KEY (org_id,workspace_id,installation_pk)
          REFERENCES bundle_installation(org_id,project_id,installation_pk)
          ON DELETE RESTRICT,
        CONSTRAINT fk_ontology_overlay_receipt_revision
          FOREIGN KEY (
            org_id,workspace_id,installation_pk,target_kind,target_id,resulting_ontology_revision
          ) REFERENCES ontology_overlay(
            org_id,workspace_id,installation_pk,target_kind,target_id,ontology_revision
          ) ON DELETE RESTRICT,
        CONSTRAINT fk_ontology_overlay_receipt_workspace
          FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT,
        CHECK (resulting_ontology_revision=expected_ontology_revision+1)
      );

      ALTER TABLE ontology_overlay ENABLE ROW LEVEL SECURITY;
      ALTER TABLE ontology_overlay FORCE ROW LEVEL SECURITY;
      CREATE POLICY tenant_scope_ontology_overlay_read ON ontology_overlay
        FOR SELECT TO aos_runtime USING (
          org_id=current_setting('aos.org_id',true)
          AND workspace_id=current_setting('aos.project_id',true)
        );
      CREATE POLICY tenant_scope_ontology_overlay_insert ON ontology_overlay
        FOR INSERT TO aos_runtime WITH CHECK (
          org_id=current_setting('aos.org_id',true)
          AND workspace_id=current_setting('aos.project_id',true)
        );
      CREATE POLICY tenant_scope_ontology_overlay_update ON ontology_overlay
        FOR UPDATE TO aos_runtime USING (
          org_id=current_setting('aos.org_id',true)
          AND workspace_id=current_setting('aos.project_id',true)
        ) WITH CHECK (
          org_id=current_setting('aos.org_id',true)
          AND workspace_id=current_setting('aos.project_id',true)
        );

      ALTER TABLE ontology_overlay_receipt ENABLE ROW LEVEL SECURITY;
      ALTER TABLE ontology_overlay_receipt FORCE ROW LEVEL SECURITY;
      CREATE POLICY tenant_scope_ontology_overlay_receipt_read ON ontology_overlay_receipt
        FOR SELECT TO aos_runtime USING (
          org_id=current_setting('aos.org_id',true)
          AND workspace_id=current_setting('aos.project_id',true)
        );
      CREATE POLICY tenant_scope_ontology_overlay_receipt_insert ON ontology_overlay_receipt
        FOR INSERT TO aos_runtime WITH CHECK (
          org_id=current_setting('aos.org_id',true)
          AND workspace_id=current_setting('aos.project_id',true)
        );

      GRANT SELECT,INSERT,UPDATE ON ontology_overlay TO aos_runtime;
      GRANT SELECT,INSERT ON ontology_overlay_receipt TO aos_runtime;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE ontology_overlay_receipt;")
    op.execute("DROP TABLE ontology_overlay;")
    op.execute("DROP FUNCTION guard_ontology_overlay_history();")
