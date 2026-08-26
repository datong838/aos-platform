"""Add tenant-bound DataRequirement and Fulfillment authorities.

Revision ID: biw2_001
Revises: w7_006
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "biw2_001"
down_revision: str | Sequence[str] | None = "w7_006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "data_requirement_head",
    "data_requirement_revision",
    "data_requirement_event",
    "data_requirement_outbox",
    "data_fulfillment_receipt",
)
APPEND_ONLY_TABLES = TABLES[1:]


def _protect(table: str, *, append_only: bool) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_biw2_001 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")
    op.execute(f"REVOKE UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")
    if append_only:
        op.execute(
            f"""CREATE TRIGGER trg_{table}_append_only_biw2_001
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
        )
        op.execute(
            f"""CREATE TRIGGER trg_{table}_truncate_guard_biw2_001
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
        )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE data_requirement_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          requirement_id TEXT NOT NULL, current_revision BIGINT NOT NULL,
          current_content_hash CHAR(64) NOT NULL, status TEXT NOT NULL,
          version BIGINT NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,requirement_id),
          CHECK(current_revision>=1), CHECK(version>=1),
          CHECK(current_content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(status IN ('requested','accepted','planned','fulfilled','rejected','cancelled','unknown'))
        )"""
    )
    op.execute(
        """CREATE TABLE data_requirement_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          requirement_id TEXT NOT NULL, revision BIGINT NOT NULL,
          prior_revision BIGINT, content_hash CHAR(64) NOT NULL,
          status TEXT NOT NULL, operation TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          case_ref JSONB NOT NULL, run_ref JSONB NOT NULL,
          checkpoint_ref JSONB NOT NULL, payload JSONB NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,requirement_id,revision),
          UNIQUE(org_id,project_id,requirement_id,content_hash),
          UNIQUE(org_id,project_id,operation,idempotency_key),
          FOREIGN KEY(org_id,project_id,requirement_id)
            REFERENCES data_requirement_head(org_id,project_id,requirement_id)
            DEFERRABLE INITIALLY DEFERRED,
          CHECK(revision>=1),
          CHECK((revision=1 AND prior_revision IS NULL) OR (revision>1 AND prior_revision=revision-1)),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(status IN ('requested','accepted','planned','fulfilled','rejected','cancelled','unknown')),
          CHECK(jsonb_typeof(case_ref)='object'), CHECK(jsonb_typeof(run_ref)='object'),
          CHECK(jsonb_typeof(checkpoint_ref)='object'), CHECK(jsonb_typeof(payload)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE data_requirement_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          requirement_id TEXT NOT NULL, requirement_revision BIGINT NOT NULL,
          event_id TEXT NOT NULL, sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
          from_status TEXT, to_status TEXT NOT NULL, payload JSONB NOT NULL,
          content_hash CHAR(64) NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,event_id),
          UNIQUE(org_id,project_id,requirement_id,sequence),
          FOREIGN KEY(org_id,project_id,requirement_id,requirement_revision)
            REFERENCES data_requirement_revision(org_id,project_id,requirement_id,revision),
          CHECK(sequence>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(payload)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE data_requirement_outbox (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          outbox_id TEXT NOT NULL, requirement_id TEXT NOT NULL,
          requirement_revision BIGINT NOT NULL, event_id TEXT NOT NULL,
          topic TEXT NOT NULL, payload JSONB NOT NULL,
          content_hash CHAR(64) NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,outbox_id),
          UNIQUE(org_id,project_id,event_id,topic),
          FOREIGN KEY(org_id,project_id,event_id)
            REFERENCES data_requirement_event(org_id,project_id,event_id),
          FOREIGN KEY(org_id,project_id,requirement_id,requirement_revision)
            REFERENCES data_requirement_revision(org_id,project_id,requirement_id,revision),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(payload)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE data_fulfillment_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          fulfillment_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          requirement_id TEXT NOT NULL, requirement_revision BIGINT NOT NULL,
          status TEXT NOT NULL, artifact_refs JSONB NOT NULL,
          source_readiness_ref JSONB NOT NULL, cutoff_at TIMESTAMPTZ NOT NULL,
          fulfilled_at TIMESTAMPTZ NOT NULL, content_hash CHAR(64) NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,fulfillment_id),
          UNIQUE(org_id,project_id,receipt_id),
          FOREIGN KEY(org_id,project_id,requirement_id,requirement_revision)
            REFERENCES data_requirement_revision(org_id,project_id,requirement_id,revision),
          CHECK(status IN ('fulfilled','partial','rejected','unknown')),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(fulfilled_at>=cutoff_at),
          CHECK(jsonb_typeof(artifact_refs)='array'),
          CHECK(jsonb_typeof(source_readiness_ref)='object')
        )"""
    )
    op.execute(
        "CREATE INDEX idx_data_requirement_head_status_biw2_001 "
        "ON data_requirement_head(org_id,project_id,status,updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_data_requirement_event_sequence_biw2_001 "
        "ON data_requirement_event(org_id,project_id,requirement_id,sequence DESC)"
    )
    op.execute(
        "CREATE INDEX idx_data_requirement_outbox_topic_biw2_001 "
        "ON data_requirement_outbox(org_id,project_id,topic,created_at)"
    )
    for table in TABLES:
        _protect(table, append_only=table in APPEND_ONLY_TABLES)


def downgrade() -> None:
    nonempty = " OR ".join(
        f"EXISTS (SELECT 1 FROM {table} LIMIT 1)" for table in TABLES
    )
    op.execute(
        f"""DO $$ BEGIN
          IF {nonempty} THEN
            RAISE EXCEPTION 'cannot downgrade biw2_001 with DataRequirement authority data'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
