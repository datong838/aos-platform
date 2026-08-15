"""Add governed Analyst QueryJob and Result authority.

Revision ID: aip8_001
Revises: bind1_003
Create Date: 2026-08-15
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip8_001"
down_revision: str | Sequence[str] | None = "bind1_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "aip_analyst_query_job",
    "aip_analyst_query_event",
    "aip_analyst_query_result_revision",
    "aip_analyst_query_receipt",
)


def upgrade() -> None:
    op.execute("""CREATE FUNCTION guard_aip8_append_only() RETURNS trigger AS $$
      BEGIN RAISE EXCEPTION 'AIP8_APPEND_ONLY' USING ERRCODE='55000'; END;
      $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TABLE aip_analyst_query_job (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, query_id TEXT NOT NULL,
      kind TEXT NOT NULL, request_json JSONB NOT NULL, request_hash TEXT NOT NULL,
      cutoff_at TIMESTAMPTZ NOT NULL, deadline_at TIMESTAMPTZ NOT NULL,
      idempotency_key TEXT NOT NULL, created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,query_id),
      UNIQUE(org_id,project_id,idempotency_key),
      CHECK(kind IN ('semantic','knowledge','metric')), CHECK(length(request_hash)=64),
      CHECK(deadline_at>cutoff_at))""")
    op.execute("""CREATE TABLE aip_analyst_query_event (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
      query_id TEXT NOT NULL, sequence BIGINT NOT NULL, event_kind TEXT NOT NULL,
      status TEXT NOT NULL, reason_code TEXT, event_hash TEXT NOT NULL,
      actor TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,event_id), UNIQUE(org_id,project_id,query_id,sequence),
      CHECK(sequence>=1), CHECK(length(event_hash)=64),
      CHECK(event_kind IN ('created','started','result_recorded','cancelled','timed_out','failed','reconciled')),
      CHECK(status IN ('queued','running','succeeded','failed','cancelled','timed_out')),
      FOREIGN KEY(org_id,project_id,query_id) REFERENCES aip_analyst_query_job(org_id,project_id,query_id))""")
    op.execute("""CREATE TABLE aip_analyst_query_result_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, query_id TEXT NOT NULL,
      revision BIGINT NOT NULL, status TEXT NOT NULL, result_json JSONB NOT NULL,
      content_hash TEXT NOT NULL, cutoff_at TIMESTAMPTZ NOT NULL,
      created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,query_id,revision), UNIQUE(org_id,project_id,query_id,content_hash),
      CHECK(revision>=1), CHECK(length(content_hash)=64),
      CHECK(status IN ('complete','empty','degraded','partial','blocked')),
      FOREIGN KEY(org_id,project_id,query_id) REFERENCES aip_analyst_query_job(org_id,project_id,query_id))""")
    op.execute("""CREATE TABLE aip_analyst_query_receipt (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, operation TEXT NOT NULL,
      idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL, query_id TEXT NOT NULL,
      resulting_sequence BIGINT NOT NULL, resulting_revision BIGINT,
      response_json JSONB NOT NULL, actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,operation,idempotency_key), CHECK(length(request_hash)=64),
      CHECK(resulting_sequence>=1), CHECK(resulting_revision IS NULL OR resulting_revision>=1),
      FOREIGN KEY(org_id,project_id,query_id) REFERENCES aip_analyst_query_job(org_id,project_id,query_id))""")
    op.execute("CREATE INDEX aip_analyst_query_event_latest_idx ON aip_analyst_query_event(org_id,project_id,query_id,sequence DESC)")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_aip8 ON {table} TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_aip8_append_only()")
        op.execute(f"CREATE TRIGGER trg_{table}_truncate_guard BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION guard_aip8_append_only()")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("DROP FUNCTION IF EXISTS guard_aip8_append_only()")
