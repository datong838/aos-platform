"""O1-UA2 tenant-authoritative knowledge, action, task and evidence records.

Revision ID: o1ua2_001
Revises: o1d_002
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1ua2_001"
down_revision: str | Sequence[str] | None = "o1d_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECORD_KINDS = (
    "knowledge", "action_type", "action_instance", "task",
    "artifact", "eval", "evidence", "retention_policy",
)


def upgrade() -> None:
    op.execute("""
      CREATE FUNCTION guard_ontology_operational_revision()
      RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        RAISE EXCEPTION 'ONTOLOGY_OPERATIONAL_REVISION_IMMUTABLE' USING ERRCODE='55000';
      END $$;
      CREATE FUNCTION verify_ontology_operational_revision_insert()
      RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.payload_hash IS DISTINCT FROM encode(
          digest(convert_to(canonical_asset_registry_jsonb(NEW.payload),'UTF8'),'sha256'),'hex'
        ) THEN
          RAISE EXCEPTION 'ONTOLOGY_OPERATIONAL_PAYLOAD_HASH_MISMATCH' USING ERRCODE='22000';
        END IF;
        RETURN NEW;
      END $$;
    """)
    for kind in RECORD_KINDS:
        head = f"ontology_{kind}_head"
        revision_table = f"ontology_{kind}_revision"
        op.execute(f"""
          CREATE TABLE {head} (
            org_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            record_id TEXT NOT NULL CHECK (BTRIM(record_id)<>''),
            active_revision INTEGER NOT NULL DEFAULT 0 CHECK (active_revision>=0),
            archived_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (org_id,workspace_id,record_id),
            CONSTRAINT fk_{head}_workspace FOREIGN KEY (org_id,workspace_id)
              REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT,
            CHECK (updated_at>=created_at)
          );
          CREATE TABLE {revision_table} (
            org_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            record_id TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision>=1),
            payload JSONB NOT NULL CHECK (jsonb_typeof(payload)='object'),
            payload_hash CHAR(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{{64}}$'),
            supersedes_revision INTEGER,
            revokes_revision INTEGER,
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
          CREATE TRIGGER trg_{revision_table}_immutable
            BEFORE UPDATE OR DELETE ON {revision_table}
            FOR EACH ROW EXECUTE FUNCTION guard_ontology_operational_revision();
          CREATE TRIGGER trg_{revision_table}_hash
            BEFORE INSERT ON {revision_table}
            FOR EACH ROW EXECUTE FUNCTION verify_ontology_operational_revision_insert();
          CREATE INDEX idx_{revision_table}_latest
            ON {revision_table}(org_id,workspace_id,record_id,revision DESC);
        """)

    op.execute("""
      CREATE TABLE ontology_authority_receipt (
        org_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL CHECK (BTRIM(idempotency_key)<>''),
        request_hash CHAR(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
        record_kind TEXT NOT NULL CHECK (record_kind IN (
          'knowledge','action_type','action_instance','task','artifact','eval','evidence','retention_policy'
        )),
        record_id TEXT NOT NULL CHECK (BTRIM(record_id)<>''),
        expected_revision INTEGER NOT NULL CHECK (expected_revision>=0),
        resulting_revision INTEGER NOT NULL CHECK (resulting_revision=expected_revision+1),
        response_etag TEXT NOT NULL CHECK (BTRIM(response_etag)<>''),
        result_json JSONB NOT NULL CHECK (jsonb_typeof(result_json)='object'),
        actor TEXT NOT NULL CHECK (BTRIM(actor)<>''),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,idempotency_key),
        CONSTRAINT fk_ontology_authority_receipt_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT
      );
      CREATE TABLE ontology_evidence_cleanup_receipt (
        org_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        cleanup_id UUID NOT NULL DEFAULT gen_random_uuid(),
        evidence_id TEXT NOT NULL,
        evidence_revision INTEGER NOT NULL CHECK (evidence_revision>=1),
        content_hash CHAR(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
        policy_id TEXT NOT NULL,
        policy_revision INTEGER NOT NULL CHECK (policy_revision>=1),
        actor TEXT NOT NULL CHECK (BTRIM(actor)<>''),
        cleaned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id,workspace_id,cleanup_id),
        CONSTRAINT fk_ontology_evidence_cleanup_evidence FOREIGN KEY (
          org_id,workspace_id,evidence_id,evidence_revision
        ) REFERENCES ontology_evidence_revision(org_id,workspace_id,record_id,revision) ON DELETE RESTRICT,
        CONSTRAINT fk_ontology_evidence_cleanup_policy FOREIGN KEY (
          org_id,workspace_id,policy_id,policy_revision
        ) REFERENCES ontology_retention_policy_revision(org_id,workspace_id,record_id,revision) ON DELETE RESTRICT,
        CONSTRAINT fk_ontology_evidence_cleanup_workspace FOREIGN KEY (org_id,workspace_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT
      );
    """)

    tables = [
        *(f"ontology_{kind}_{suffix}" for kind in RECORD_KINDS for suffix in ("head", "revision")),
        "ontology_authority_receipt", "ontology_evidence_cleanup_receipt",
    ]
    for table in tables:
        op.execute(f"""
          ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
          ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
          CREATE POLICY tenant_scope_{table} ON {table} TO aos_runtime
            USING (org_id=current_setting('aos.org_id',true)
               AND workspace_id=current_setting('aos.project_id',true))
            WITH CHECK (org_id=current_setting('aos.org_id',true)
               AND workspace_id=current_setting('aos.project_id',true));
          GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime;
        """)


def downgrade() -> None:
    op.execute("DROP TABLE ontology_evidence_cleanup_receipt;")
    op.execute("DROP TABLE ontology_authority_receipt;")
    for kind in reversed(RECORD_KINDS):
        op.execute(f"DROP TABLE ontology_{kind}_revision;")
        op.execute(f"DROP TABLE ontology_{kind}_head;")
    op.execute("DROP FUNCTION guard_ontology_operational_revision();")
    op.execute("DROP FUNCTION verify_ontology_operational_revision_insert();")
