"""Add media attempt Capacity/Budget/Usage/Settlement authority (W7-08).

Revision ID: w7_006
Revises: w7_005
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w7_006"
down_revision: str | Sequence[str] | None = "w7_005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _protect(table: str) -> str:
    return f"""
    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope_{table}_w7_006 ON {table} TO aos_runtime
      USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''));
    GRANT SELECT,INSERT ON {table} TO aos_runtime;
    REVOKE UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime;
    CREATE TRIGGER trg_{table}_append_only_w7_006
      BEFORE UPDATE OR DELETE ON {table}
      FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only();
    CREATE TRIGGER trg_{table}_truncate_guard_w7_006
      BEFORE TRUNCATE ON {table}
      FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only();
    """


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_media_attempt_finance (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, finance_id TEXT NOT NULL,
          job_id TEXT NOT NULL, attempt_binding_hash CHAR(64) NOT NULL,
          base_payload JSONB NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,finance_id),
          UNIQUE(org_id,project_id,attempt_binding_hash),
          UNIQUE(org_id,project_id,job_id),
          FOREIGN KEY(org_id,project_id,job_id)
            REFERENCES aip_media_provider_job(org_id,project_id,job_id),
          CHECK(attempt_binding_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(base_payload)='object'),
          CHECK(base_payload->>'currency' ~ '^[A-Z]{3}$'),
          CHECK((base_payload->>'projectedMinMinor')::BIGINT>=0),
          CHECK((base_payload->>'projectedMaxMinor')::BIGINT>=(base_payload->>'projectedMinMinor')::BIGINT)
        );

        CREATE TABLE aip_media_attempt_finance_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, finance_id TEXT NOT NULL,
          version BIGINT NOT NULL, event_kind TEXT NOT NULL, payload JSONB NOT NULL,
          content_hash CHAR(64) NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,finance_id,version),
          UNIQUE(org_id,project_id,finance_id,content_hash),
          FOREIGN KEY(org_id,project_id,finance_id)
            REFERENCES aip_media_attempt_finance(org_id,project_id,finance_id),
          CHECK(version>=1),
          CHECK(event_kind IN ('prepared','capacity_consumed','capacity_released','cancel_observed','usage_bound','settled')),
          CHECK(jsonb_typeof(payload)='object'),
          CHECK(content_hash ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE aip_media_attempt_finance_idempotency (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, operation TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          result_ref JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,operation,idempotency_key),
          CHECK(char_length(idempotency_key) BETWEEN 1 AND 120),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(result_ref)='object')
        );

        CREATE INDEX idx_media_finance_job_w7_006
          ON aip_media_attempt_finance(org_id,project_id,job_id,created_at DESC);
        CREATE INDEX idx_media_finance_event_kind_w7_006
          ON aip_media_attempt_finance_event(org_id,project_id,event_kind,created_at DESC);
        """
    )
    for table in (
        "aip_media_attempt_finance",
        "aip_media_attempt_finance_event",
        "aip_media_attempt_finance_idempotency",
    ):
        op.execute(_protect(table))


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_media_attempt_finance LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_media_attempt_finance_event LIMIT 1)
          THEN RAISE EXCEPTION 'cannot downgrade w7_006 with media finance authority data'
            USING ERRCODE='55000'; END IF;
        END $$;
        DROP TABLE aip_media_attempt_finance_idempotency;
        DROP TABLE aip_media_attempt_finance_event;
        DROP TABLE aip_media_attempt_finance;
        """
    )
