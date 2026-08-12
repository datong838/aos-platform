"""Add the governed AIP memory authority tables.

Revision ID: aip5_001
Revises: aip4_008
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip5_001"
down_revision: str | Sequence[str] | None = "aip4_008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "aip_memory_source_revision",
    "aip_memory_candidate",
    "aip_memory_candidate_event",
    "aip_memory_item",
    "aip_memory_item_revision",
)

_APPEND_ONLY_TABLES = (
    "aip_memory_source_revision",
    "aip_memory_candidate_event",
    "aip_memory_item_revision",
)


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_memory_source_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          source_id TEXT NOT NULL, revision BIGINT NOT NULL,
          source_kind TEXT NOT NULL, source_uri TEXT, source_ref JSONB,
          observed_at TIMESTAMPTZ NOT NULL,
          freshness_expires_at TIMESTAMPTZ NOT NULL,
          license_id TEXT NOT NULL, usage_policy TEXT NOT NULL,
          content_hash TEXT NOT NULL, provider TEXT NOT NULL,
          provider_version TEXT NOT NULL, applicability JSONB NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,source_id,revision),
          UNIQUE (org_id,project_id,source_id,content_hash),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (freshness_expires_at > observed_at),
          CHECK ((source_uri IS NULL) <> (source_ref IS NULL)),
          CHECK (source_kind IN (
            'authorized_document','task_evidence','effect_review',
            'research_artifact','professional_database',
            'customer_aggregate','human_experience'
          )),
          CHECK (jsonb_typeof(applicability)='array'
             AND jsonb_array_length(applicability) > 0),
          FOREIGN KEY (org_id,project_id)
            REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_candidate (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          candidate_id TEXT NOT NULL, memory_layer TEXT NOT NULL,
          scope TEXT NOT NULL, status TEXT NOT NULL,
          task_id TEXT NOT NULL, run_id TEXT NOT NULL,
          subject_ref JSONB NOT NULL, payload_ref JSONB NOT NULL,
          source_id TEXT NOT NULL, source_revision BIGINT NOT NULL,
          confidence DOUBLE PRECISION NOT NULL, markings JSONB NOT NULL,
          quarantine_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
          eval_report_ref JSONB, draft_ref JSONB, approval_event_ref JSONB,
          version BIGINT NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,candidate_id),
          CHECK (memory_layer IN ('episodic','semantic')),
          CHECK (scope IN ('public_package','organization','workspace')),
          CHECK (status IN ('pending','quarantined','rejected','approved','promoted')),
          CHECK (confidence >= 0 AND confidence <= 1), CHECK (version >= 1),
          CHECK (jsonb_typeof(markings)='array' AND jsonb_array_length(markings)>0),
          CHECK (jsonb_typeof(quarantine_reasons)='array'),
          CHECK (status<>'quarantined' OR jsonb_array_length(quarantine_reasons)>0),
          CHECK ((status NOT IN ('approved','promoted')) OR
            (eval_report_ref IS NOT NULL AND draft_ref IS NOT NULL
             AND approval_event_ref IS NOT NULL)),
          FOREIGN KEY (org_id,project_id,source_id,source_revision)
            REFERENCES aip_memory_source_revision(org_id,project_id,source_id,revision),
          FOREIGN KEY (org_id,project_id,task_id)
            REFERENCES aip_task(org_id,project_id,task_id),
          FOREIGN KEY (org_id,project_id,run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_candidate_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          event_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
          sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
          from_status TEXT, to_status TEXT NOT NULL,
          reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
          evidence_ref JSONB, event_hash TEXT NOT NULL,
          actor TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,event_id),
          UNIQUE (org_id,project_id,candidate_id,sequence),
          CHECK (sequence >= 1), CHECK (event_hash ~ '^[0-9a-f]{64}$'),
          CHECK (event_type IN ('submitted','quarantined','rejected','approved','promoted')),
          CHECK (from_status IS NULL OR from_status IN
            ('pending','quarantined','rejected','approved','promoted')),
          CHECK (to_status IN ('pending','quarantined','rejected','approved','promoted')),
          CHECK (jsonb_typeof(reason_codes)='array'),
          FOREIGN KEY (org_id,project_id,candidate_id)
            REFERENCES aip_memory_candidate(org_id,project_id,candidate_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_item (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          memory_item_id TEXT NOT NULL, memory_layer TEXT NOT NULL,
          scope TEXT NOT NULL, status TEXT NOT NULL,
          subject_ref JSONB NOT NULL, current_revision BIGINT NOT NULL,
          version BIGINT NOT NULL DEFAULT 1,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,memory_item_id),
          CHECK (memory_layer IN ('episodic','semantic')),
          CHECK (scope IN ('public_package','organization','workspace')),
          CHECK (status IN ('active','stale','revoked','expired')),
          CHECK (current_revision >= 1), CHECK (version >= 1),
          FOREIGN KEY (org_id,project_id)
            REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_item_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          memory_item_id TEXT NOT NULL, revision BIGINT NOT NULL,
          candidate_id TEXT NOT NULL, source_id TEXT NOT NULL,
          source_revision BIGINT NOT NULL, payload_ref JSONB NOT NULL,
          content_hash TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
          applicability JSONB NOT NULL, markings JSONB NOT NULL,
          effective_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,memory_item_id,revision),
          UNIQUE (org_id,project_id,memory_item_id,content_hash),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (confidence >= 0 AND confidence <= 1),
          CHECK (expires_at IS NULL OR expires_at > effective_at),
          CHECK (jsonb_typeof(applicability)='array'
             AND jsonb_array_length(applicability)>0),
          CHECK (jsonb_typeof(markings)='array' AND jsonb_array_length(markings)>0),
          FOREIGN KEY (org_id,project_id,memory_item_id)
            REFERENCES aip_memory_item(org_id,project_id,memory_item_id),
          FOREIGN KEY (org_id,project_id,candidate_id)
            REFERENCES aip_memory_candidate(org_id,project_id,candidate_id),
          FOREIGN KEY (org_id,project_id,source_id,source_revision)
            REFERENCES aip_memory_source_revision(org_id,project_id,source_id,revision)
        )"""
    )
    op.execute(
        """ALTER TABLE aip_memory_item
        ADD CONSTRAINT aip_memory_item_current_revision_fk
        FOREIGN KEY (org_id,project_id,memory_item_id,current_revision)
        REFERENCES aip_memory_item_revision
          (org_id,project_id,memory_item_id,revision)
        DEFERRABLE INITIALLY DEFERRED"""
    )

    op.execute(
        """CREATE INDEX aip_memory_candidate_status_idx
        ON aip_memory_candidate(org_id,project_id,status,updated_at,candidate_id)"""
    )
    op.execute(
        """CREATE INDEX aip_memory_item_subject_idx
        ON aip_memory_item(org_id,project_id,status,memory_layer,memory_item_id)"""
    )
    op.execute(
        """CREATE INDEX aip_memory_source_freshness_idx
        ON aip_memory_source_revision
          (org_id,project_id,freshness_expires_at,source_id,revision)"""
    )

    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_aip5 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )

    op.execute(
        """CREATE FUNCTION guard_aip5_memory_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'AIP5_MEMORY_APPEND_ONLY' USING ERRCODE='55000';
        END;
        $$ LANGUAGE plpgsql"""
    )
    for table in _APPEND_ONLY_TABLES:
        op.execute(
            f"""CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip5_memory_append_only()"""
        )
        op.execute(
            f"""CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_aip5_memory_append_only()"""
        )

    for table in _APPEND_ONLY_TABLES:
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")
    for table in ("aip_memory_candidate", "aip_memory_item"):
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime")


def downgrade() -> None:
    op.execute(
        """ALTER TABLE aip_memory_item
        DROP CONSTRAINT IF EXISTS aip_memory_item_current_revision_fk"""
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("DROP FUNCTION IF EXISTS guard_aip5_memory_append_only()")
