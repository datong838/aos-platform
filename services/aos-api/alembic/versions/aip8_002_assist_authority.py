"""Add append-only Assist thread, turn, event and receipt authority.

Revision ID: aip8_002
Revises: aip8_001
Create Date: 2026-08-16
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip8_002"
down_revision: str | Sequence[str] | None = "aip8_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "aip_assist_thread",
    "aip_assist_turn",
    "aip_assist_event",
    "aip_assist_receipt",
)


def upgrade() -> None:
    op.execute("""CREATE FUNCTION guard_aip8_assist_append_only() RETURNS trigger AS $$
      BEGIN RAISE EXCEPTION 'AIP8_ASSIST_APPEND_ONLY' USING ERRCODE='55000'; END;
      $$ LANGUAGE plpgsql""")
    op.execute("""CREATE FUNCTION guard_aip8_assist_event_insert() RETURNS trigger AS $$
      DECLARE previous_sequence BIGINT; previous_type TEXT;
      BEGIN
        SELECT sequence,event_type INTO previous_sequence,previous_type
        FROM aip_assist_event
        WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND thread_id=NEW.thread_id AND turn_id=NEW.turn_id
        ORDER BY sequence DESC LIMIT 1 FOR UPDATE;
        IF previous_sequence IS NULL AND NEW.sequence <> 1 THEN
          RAISE EXCEPTION 'AIP8_ASSIST_EVENT_SEQUENCE' USING ERRCODE='23514';
        ELSIF previous_sequence IS NOT NULL AND NEW.sequence <> previous_sequence + 1 THEN
          RAISE EXCEPTION 'AIP8_ASSIST_EVENT_SEQUENCE' USING ERRCODE='23514';
        ELSIF previous_type IN ('blocked','done','error') THEN
          RAISE EXCEPTION 'AIP8_ASSIST_EVENT_AFTER_TERMINAL' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END;
      $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TABLE aip_assist_thread (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, thread_id TEXT NOT NULL,
      subject_json JSONB NOT NULL, subject_hash TEXT NOT NULL,
      idempotency_key TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,thread_id),
      UNIQUE(org_id,project_id,idempotency_key),
      CHECK(length(subject_hash)=64))""")
    op.execute("""CREATE TABLE aip_assist_turn (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, thread_id TEXT NOT NULL,
      turn_id TEXT NOT NULL, turn_sequence BIGINT NOT NULL,
      request_json JSONB NOT NULL, request_hash TEXT NOT NULL,
      cutoff_at TIMESTAMPTZ NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,thread_id,turn_id),
      UNIQUE(org_id,project_id,thread_id,turn_sequence),
      CHECK(turn_sequence>=1), CHECK(length(request_hash)=64),
      FOREIGN KEY(org_id,project_id,thread_id)
        REFERENCES aip_assist_thread(org_id,project_id,thread_id))""")
    op.execute("""CREATE TABLE aip_assist_event (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
      thread_id TEXT NOT NULL, turn_id TEXT NOT NULL, sequence BIGINT NOT NULL,
      event_type TEXT NOT NULL, event_json JSONB NOT NULL, event_hash TEXT NOT NULL,
      actor TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,event_id),
      UNIQUE(org_id,project_id,thread_id,turn_id,sequence),
      CHECK(sequence>=1), CHECK(length(event_hash)=64),
      CHECK(event_type IN ('start','context','blocked','delta','proposal','done','error')),
      FOREIGN KEY(org_id,project_id,thread_id,turn_id)
        REFERENCES aip_assist_turn(org_id,project_id,thread_id,turn_id))""")
    op.execute("""CREATE TABLE aip_assist_receipt (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, operation TEXT NOT NULL,
      idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
      thread_id TEXT NOT NULL, turn_id TEXT, response_json JSONB NOT NULL,
      actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,operation,idempotency_key),
      CHECK(operation IN ('create_thread','create_turn')),
      CHECK(length(request_hash)=64),
      FOREIGN KEY(org_id,project_id,thread_id)
        REFERENCES aip_assist_thread(org_id,project_id,thread_id))""")
    op.execute("CREATE INDEX aip_assist_turn_latest_idx ON aip_assist_turn(org_id,project_id,thread_id,turn_sequence DESC)")
    op.execute("CREATE INDEX aip_assist_event_latest_idx ON aip_assist_event(org_id,project_id,thread_id,turn_id,sequence DESC)")
    op.execute("""CREATE TRIGGER trg_aip_assist_event_sequence
      BEFORE INSERT ON aip_assist_event FOR EACH ROW
      EXECUTE FUNCTION guard_aip8_assist_event_insert()""")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_aip8 ON {table} TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_aip8_assist_append_only()")
        op.execute(f"CREATE TRIGGER trg_{table}_truncate_guard BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION guard_aip8_assist_append_only()")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("DROP FUNCTION IF EXISTS guard_aip8_assist_event_insert()")
    op.execute("DROP FUNCTION IF EXISTS guard_aip8_assist_append_only()")
