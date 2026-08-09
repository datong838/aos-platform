"""O1-R1: replace the empty O1-A0 DLQ shell with the reviewed PG contract.

Revision ID: o1r1_002
Revises: o1r1_001
Create Date: 2026-08-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1r1_002"
down_revision: str | Sequence[str] | None = "o1r1_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE ecom_dlq_retry_event RENAME TO ecom_dlq_retry_event_legacy_o1a0;")
    op.execute("ALTER TABLE ecom_dlq_retry_receipt RENAME TO ecom_dlq_retry_receipt_legacy_o1a0;")
    op.execute("ALTER TABLE ecom_dlq RENAME TO ecom_dlq_legacy_o1a0;")

    op.execute("""
        CREATE TABLE ecom_dlq (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          dlq_id UUID NOT NULL,
          idempotency_key TEXT NOT NULL,
          pipeline_id TEXT NOT NULL,
          error_code TEXT NOT NULL,
          source_error_code TEXT,
          reason TEXT NOT NULL DEFAULT '',
          metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
          payload_hash CHAR(64) NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          retry_count INTEGER NOT NULL DEFAULT 0,
          max_retry INTEGER NOT NULL DEFAULT 3,
          last_retry_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (org_id, workspace_id, dlq_id),
          UNIQUE (org_id, workspace_id, idempotency_key),
          CONSTRAINT ck_ecom_dlq_payload_hash
            CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_ecom_dlq_error_code
            CHECK (error_code IN ('SOURCE_CONNECTION_ERROR','STORE_CONFLICT','VALIDATION_ERROR')),
          CONSTRAINT ck_ecom_dlq_source_error_code CHECK (
            source_error_code IS NULL OR source_error_code IN (
              'IDEMPOTENCY_CONFLICT','CONCURRENT_WRITE_CONFLICT','SOURCE_VERSION_CONFLICT',
              'DANGLING_LINK','CHECKPOINT_CAS_CONFLICT','CHECKPOINT_BOUNDARY_INVALID',
              'CHECKPOINT_REGRESSION','CONNECTION_ERROR','TIMEOUT','OS_ERROR',
              'SQL_INTEGRITY_ERROR','VALUE_ERROR','KEY_ERROR','TYPE_ERROR',
              'UNCLASSIFIED_EXCEPTION'
            )
          ),
          CONSTRAINT ck_ecom_dlq_status
            CHECK (status IN ('open','retrying','retried','failed','archived')),
          CONSTRAINT ck_ecom_dlq_retry
            CHECK (retry_count >= 0 AND max_retry >= 1 AND retry_count <= max_retry),
          CONSTRAINT ck_ecom_dlq_time CHECK (updated_at >= created_at),
          CONSTRAINT fk_ecom_dlq_workspace
            FOREIGN KEY (org_id, workspace_id)
            REFERENCES twa_workspace(org_id, project_id) ON DELETE RESTRICT
        );
    """)
    op.execute("""
        CREATE TABLE ecom_dlq_retry_receipt (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          dlq_id UUID NOT NULL,
          retry_idempotency_key TEXT NOT NULL,
          request_hash CHAR(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          attempt_no INTEGER NOT NULL CHECK (attempt_no >= 1),
          accepted_from_status TEXT NOT NULL,
          actor TEXT NOT NULL CHECK (BTRIM(actor) <> ''),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (org_id, workspace_id, dlq_id, retry_idempotency_key),
          UNIQUE (org_id, workspace_id, dlq_id, attempt_no),
          FOREIGN KEY (org_id, workspace_id, dlq_id)
            REFERENCES ecom_dlq(org_id, workspace_id, dlq_id) ON DELETE RESTRICT,
          FOREIGN KEY (org_id, workspace_id)
            REFERENCES twa_workspace(org_id, project_id) ON DELETE RESTRICT
        );
        CREATE TABLE ecom_dlq_retry_event (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          event_id UUID NOT NULL,
          dlq_id UUID NOT NULL,
          event_type TEXT NOT NULL CHECK (
            event_type IN ('retry_requested','retry_succeeded','retry_failed','status_changed','archived')
          ),
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (org_id, workspace_id, event_id),
          FOREIGN KEY (org_id, workspace_id, dlq_id)
            REFERENCES ecom_dlq(org_id, workspace_id, dlq_id) ON DELETE RESTRICT
        );
    """)
    for table in ("ecom_dlq", "ecom_dlq_retry_receipt", "ecom_dlq_retry_event"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY {table}_read_isolation ON {table}
              FOR SELECT TO aos_runtime
              USING (
                org_id = current_setting('aos.org_id', true)
                AND workspace_id = current_setting('aos.project_id', true)
              );
            CREATE POLICY {table}_insert_isolation ON {table}
              FOR INSERT TO aos_runtime
              WITH CHECK (
                org_id = current_setting('aos.org_id', true)
                AND workspace_id = current_setting('aos.project_id', true)
              );
        """)
    op.execute("""
        CREATE POLICY ecom_dlq_update_isolation ON ecom_dlq
          FOR UPDATE TO aos_runtime
          USING (
            org_id = current_setting('aos.org_id', true)
            AND workspace_id = current_setting('aos.project_id', true)
          )
          WITH CHECK (
            org_id = current_setting('aos.org_id', true)
            AND workspace_id = current_setting('aos.project_id', true)
          );
        GRANT SELECT, INSERT, UPDATE ON ecom_dlq TO aos_runtime;
        GRANT SELECT, INSERT ON ecom_dlq_retry_receipt TO aos_runtime;
        GRANT SELECT, INSERT ON ecom_dlq_retry_event TO aos_runtime;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ecom_dlq_retry_event CASCADE;")
    op.execute("DROP TABLE IF EXISTS ecom_dlq_retry_receipt CASCADE;")
    op.execute("DROP TABLE IF EXISTS ecom_dlq CASCADE;")
    op.execute("ALTER TABLE ecom_dlq_legacy_o1a0 RENAME TO ecom_dlq;")
    op.execute("ALTER TABLE ecom_dlq_retry_receipt_legacy_o1a0 RENAME TO ecom_dlq_retry_receipt;")
    op.execute("ALTER TABLE ecom_dlq_retry_event_legacy_o1a0 RENAME TO ecom_dlq_retry_event;")
