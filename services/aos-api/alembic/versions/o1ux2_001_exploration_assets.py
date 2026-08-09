"""O1-UX2 tenant-authoritative exploration assets.

Revision ID: o1ux2_001
Revises: o1ua2_002
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1ux2_001"
down_revision: str | Sequence[str] | None = "o1ua2_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = ("exploration", "object_set", "annotation")


def _create_kind(kind: str) -> None:
    head = f"ontology_{kind}_asset_head"
    revisions = f"ontology_{kind}_asset_revision"
    op.execute(f"""
      CREATE TABLE {head} (
        org_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
        asset_id TEXT NOT NULL CHECK (BTRIM(asset_id)<>''),
        owner_subject TEXT NOT NULL CHECK (BTRIM(owner_subject)<>''),
        active_revision INTEGER NOT NULL DEFAULT 0 CHECK (active_revision>=0),
        archived_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,asset_id),
        CONSTRAINT fk_{head}_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT,
        CHECK (updated_at>=created_at)
      );
      CREATE TABLE {revisions} (
        org_id TEXT NOT NULL, workspace_id TEXT NOT NULL, asset_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision>=1),
        payload JSONB NOT NULL CHECK (jsonb_typeof(payload)='object'),
        payload_hash CHAR(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{{64}}$'),
        created_by TEXT NOT NULL CHECK (BTRIM(created_by)<>''),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,asset_id,revision),
        CONSTRAINT fk_{revisions}_head FOREIGN KEY (org_id,workspace_id,asset_id)
          REFERENCES {head}(org_id,workspace_id,asset_id) ON DELETE RESTRICT,
        CONSTRAINT fk_{revisions}_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT
      );
      CREATE TRIGGER trg_{revisions}_immutable BEFORE UPDATE OR DELETE ON {revisions}
        FOR EACH ROW EXECUTE FUNCTION guard_ontology_operational_revision();
      CREATE TRIGGER trg_{revisions}_hash BEFORE INSERT ON {revisions}
        FOR EACH ROW EXECUTE FUNCTION verify_ontology_operational_revision_insert();
      CREATE INDEX idx_{revisions}_latest
        ON {revisions}(org_id,workspace_id,asset_id,revision DESC);
    """)


def upgrade() -> None:
    for kind in KINDS:
        _create_kind(kind)
    op.execute("""
      CREATE TABLE ontology_object_set_item (
        org_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
        object_set_id TEXT NOT NULL, object_set_revision INTEGER NOT NULL CHECK (object_set_revision>=1),
        position INTEGER NOT NULL CHECK (position>=0),
        object_type TEXT NOT NULL CHECK (BTRIM(object_type)<>''),
        object_id TEXT NOT NULL CHECK (BTRIM(object_id)<>''),
        PRIMARY KEY (org_id,workspace_id,object_set_id,object_set_revision,position),
        UNIQUE (org_id,workspace_id,object_set_id,object_set_revision,object_type,object_id),
        CONSTRAINT fk_ontology_object_set_item_revision FOREIGN KEY (
          org_id,workspace_id,object_set_id,object_set_revision
        ) REFERENCES ontology_object_set_asset_revision(
          org_id,workspace_id,asset_id,revision
        ) ON DELETE RESTRICT,
        CONSTRAINT fk_ontology_object_set_item_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT
      );
      CREATE TRIGGER trg_ontology_object_set_item_immutable
        BEFORE UPDATE OR DELETE ON ontology_object_set_item
        FOR EACH ROW EXECUTE FUNCTION guard_ontology_operational_revision();

      CREATE TABLE ontology_exploration_asset_receipt (
        org_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL CHECK (BTRIM(idempotency_key)<>''),
        request_hash CHAR(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
        asset_kind TEXT NOT NULL CHECK (asset_kind IN ('exploration','object_set','annotation')),
        asset_id TEXT NOT NULL CHECK (BTRIM(asset_id)<>''),
        operation TEXT NOT NULL CHECK (operation IN ('append','archive','restore')),
        expected_revision INTEGER NOT NULL CHECK (expected_revision>=0),
        resulting_revision INTEGER NOT NULL CHECK (resulting_revision>=1),
        response_etag TEXT NOT NULL CHECK (BTRIM(response_etag)<>''),
        result_json JSONB NOT NULL CHECK (jsonb_typeof(result_json)='object'),
        actor TEXT NOT NULL CHECK (BTRIM(actor)<>''),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,idempotency_key),
        CONSTRAINT fk_ontology_exploration_asset_receipt_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT
      );
      CREATE TRIGGER trg_ontology_exploration_asset_receipt_immutable
        BEFORE UPDATE OR DELETE ON ontology_exploration_asset_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_ontology_operational_revision();
    """)
    tables = [
        *(f"ontology_{kind}_asset_{suffix}" for kind in KINDS for suffix in ("head", "revision")),
        "ontology_object_set_item", "ontology_exploration_asset_receipt",
    ]
    for table in tables:
        op.execute(f"""
          ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
          ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
          CREATE POLICY tenant_scope_{table} ON {table} TO aos_runtime
            USING (org_id=current_setting('aos.org_id',true) AND workspace_id=current_setting('aos.project_id',true))
            WITH CHECK (org_id=current_setting('aos.org_id',true) AND workspace_id=current_setting('aos.project_id',true));
          GRANT SELECT,INSERT ON {table} TO aos_runtime;
        """)
    for kind in KINDS:
        op.execute(f"GRANT UPDATE ON ontology_{kind}_asset_head TO aos_runtime;")


def downgrade() -> None:
    op.execute("DROP TABLE ontology_exploration_asset_receipt;")
    op.execute("DROP TABLE ontology_object_set_item;")
    for kind in reversed(KINDS):
        op.execute(f"DROP TABLE ontology_{kind}_asset_revision;")
        op.execute(f"DROP TABLE ontology_{kind}_asset_head;")
