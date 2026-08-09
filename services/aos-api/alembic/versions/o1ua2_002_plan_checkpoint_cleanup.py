"""O1-UA2 explicit Plan/Checkpoint records and cleanup idempotency.

Revision ID: o1ua2_002
Revises: o1ua2_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1ua2_002"
down_revision: str | Sequence[str] | None = "o1ua2_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_kind(kind: str) -> None:
    head = f"ontology_{kind}_head"
    revision_table = f"ontology_{kind}_revision"
    op.execute(f"""
      CREATE TABLE {head} (
        org_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
        record_id TEXT NOT NULL CHECK (BTRIM(record_id)<>''),
        active_revision INTEGER NOT NULL DEFAULT 0 CHECK (active_revision>=0),
        archived_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,record_id),
        CONSTRAINT fk_{head}_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT,
        CHECK (updated_at>=created_at)
      );
      CREATE TABLE {revision_table} (
        org_id TEXT NOT NULL, workspace_id TEXT NOT NULL, record_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision>=1),
        payload JSONB NOT NULL CHECK (jsonb_typeof(payload)='object'),
        payload_hash CHAR(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{{64}}$'),
        supersedes_revision INTEGER, revokes_revision INTEGER,
        created_by TEXT NOT NULL CHECK (BTRIM(created_by)<>''),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,record_id,revision),
        CONSTRAINT fk_{revision_table}_head FOREIGN KEY (org_id,workspace_id,record_id)
          REFERENCES {head}(org_id,workspace_id,record_id) ON DELETE RESTRICT,
        CONSTRAINT fk_{revision_table}_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT,
        CHECK (supersedes_revision IS NULL OR supersedes_revision<revision),
        CHECK (revokes_revision IS NULL OR revokes_revision<revision),
        CHECK (NOT (supersedes_revision IS NOT NULL AND revokes_revision IS NOT NULL))
      );
      CREATE TRIGGER trg_{revision_table}_immutable BEFORE UPDATE OR DELETE ON {revision_table}
        FOR EACH ROW EXECUTE FUNCTION guard_ontology_operational_revision();
      CREATE TRIGGER trg_{revision_table}_hash BEFORE INSERT ON {revision_table}
        FOR EACH ROW EXECUTE FUNCTION verify_ontology_operational_revision_insert();
      CREATE INDEX idx_{revision_table}_latest
        ON {revision_table}(org_id,workspace_id,record_id,revision DESC);
    """)
    for table in (head, revision_table):
        op.execute(f"""
          ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
          ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
          CREATE POLICY tenant_scope_{table} ON {table} TO aos_runtime
            USING (org_id=current_setting('aos.org_id',true) AND workspace_id=current_setting('aos.project_id',true))
            WITH CHECK (org_id=current_setting('aos.org_id',true) AND workspace_id=current_setting('aos.project_id',true));
          GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime;
        """)


def upgrade() -> None:
    _create_kind("plan")
    _create_kind("checkpoint")
    op.execute("""
      ALTER TABLE ontology_authority_receipt
        DROP CONSTRAINT ontology_authority_receipt_record_kind_check,
        ADD CONSTRAINT ontology_authority_receipt_record_kind_check CHECK (record_kind IN (
          'knowledge','action_type','action_instance','task','plan','checkpoint',
          'artifact','eval','evidence','retention_policy'
        ));
      ALTER TABLE ontology_evidence_cleanup_receipt
        ADD COLUMN idempotency_key TEXT,
        ADD COLUMN request_hash CHAR(64);
      UPDATE ontology_evidence_cleanup_receipt SET
        idempotency_key=cleanup_id::text,
        request_hash=encode(digest(convert_to(cleanup_id::text,'UTF8'),'sha256'),'hex')
        WHERE idempotency_key IS NULL;
      ALTER TABLE ontology_evidence_cleanup_receipt
        ALTER COLUMN idempotency_key SET NOT NULL,
        ALTER COLUMN request_hash SET NOT NULL,
        ADD CONSTRAINT ck_ontology_cleanup_idempotency CHECK (BTRIM(idempotency_key)<>''),
        ADD CONSTRAINT ck_ontology_cleanup_request_hash CHECK (request_hash ~ '^[0-9a-f]{64}$'),
        ADD CONSTRAINT uq_ontology_cleanup_idempotency UNIQUE (org_id,workspace_id,idempotency_key);
      CREATE TABLE ontology_authority_archive_receipt (
        org_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL CHECK (BTRIM(idempotency_key)<>''),
        request_hash CHAR(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
        record_kind TEXT NOT NULL CHECK (record_kind IN (
          'knowledge','action_type','action_instance','task','plan','checkpoint',
          'artifact','eval','evidence','retention_policy'
        )),
        record_id TEXT NOT NULL CHECK (BTRIM(record_id)<>''),
        expected_revision INTEGER NOT NULL CHECK (expected_revision>=1),
        result_json JSONB NOT NULL CHECK (jsonb_typeof(result_json)='object'),
        actor TEXT NOT NULL CHECK (BTRIM(actor)<>''),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,idempotency_key),
        CONSTRAINT fk_ontology_authority_archive_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT
      );
      ALTER TABLE ontology_authority_archive_receipt ENABLE ROW LEVEL SECURITY;
      ALTER TABLE ontology_authority_archive_receipt FORCE ROW LEVEL SECURITY;
      CREATE POLICY tenant_scope_ontology_authority_archive_receipt
        ON ontology_authority_archive_receipt TO aos_runtime
        USING (org_id=current_setting('aos.org_id',true) AND workspace_id=current_setting('aos.project_id',true))
        WITH CHECK (org_id=current_setting('aos.org_id',true) AND workspace_id=current_setting('aos.project_id',true));
      GRANT SELECT,INSERT ON ontology_authority_archive_receipt TO aos_runtime;

      CREATE TRIGGER trg_ontology_authority_receipt_immutable
        BEFORE UPDATE OR DELETE ON ontology_authority_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_ontology_operational_revision();
      CREATE TRIGGER trg_ontology_cleanup_receipt_immutable
        BEFORE UPDATE OR DELETE ON ontology_evidence_cleanup_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_ontology_operational_revision();
      CREATE TRIGGER trg_ontology_archive_receipt_immutable
        BEFORE UPDATE OR DELETE ON ontology_authority_archive_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_ontology_operational_revision();
    """)
    revision_tables = [
        *(f"ontology_{kind}_revision" for kind in (
            "knowledge", "action_type", "action_instance", "task", "plan", "checkpoint",
            "artifact", "eval", "evidence", "retention_policy",
        )),
        "ontology_authority_receipt",
        "ontology_evidence_cleanup_receipt",
        "ontology_authority_archive_receipt",
    ]
    for table in revision_tables:
        op.execute(f"REVOKE UPDATE,DELETE ON {table} FROM aos_runtime;")


def downgrade() -> None:
    op.execute("""
      DROP TABLE ontology_authority_archive_receipt;
      DROP TRIGGER trg_ontology_cleanup_receipt_immutable ON ontology_evidence_cleanup_receipt;
      DROP TRIGGER trg_ontology_authority_receipt_immutable ON ontology_authority_receipt;
      ALTER TABLE ontology_evidence_cleanup_receipt
        DROP CONSTRAINT uq_ontology_cleanup_idempotency,
        DROP CONSTRAINT ck_ontology_cleanup_request_hash,
        DROP CONSTRAINT ck_ontology_cleanup_idempotency,
        DROP COLUMN request_hash,
        DROP COLUMN idempotency_key;
      ALTER TABLE ontology_authority_receipt
        DROP CONSTRAINT ontology_authority_receipt_record_kind_check,
        ADD CONSTRAINT ontology_authority_receipt_record_kind_check CHECK (record_kind IN (
          'knowledge','action_type','action_instance','task','artifact','eval','evidence','retention_policy'
        ));
    """)
    for kind in ("checkpoint", "plan"):
        op.execute(f"DROP TABLE ontology_{kind}_revision;")
        op.execute(f"DROP TABLE ontology_{kind}_head;")
