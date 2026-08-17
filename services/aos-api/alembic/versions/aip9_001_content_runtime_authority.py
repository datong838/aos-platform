"""Add tenant-scoped MediaJob and AvatarSession runtime authority.

Revision ID: aip9_001
Revises: aip8_002
Create Date: 2026-08-16
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip9_001"
down_revision: str | Sequence[str] | None = "aip8_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "aip_media_job",
    "aip_media_job_event",
    "aip_media_job_receipt",
    "aip_avatar_session",
    "aip_avatar_session_event",
    "aip_avatar_session_receipt",
)

APPEND_ONLY_TABLES = (
    "aip_media_job_event",
    "aip_media_job_receipt",
    "aip_avatar_session_event",
    "aip_avatar_session_receipt",
)


def _tenant_scope(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_aip9 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )


def _append_only(table: str) -> None:
    op.execute(
        f"""CREATE TRIGGER trg_{table}_append_only
        BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW
        EXECUTE FUNCTION guard_aip9_content_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{table}_truncate_guard
        BEFORE TRUNCATE ON {table} FOR EACH STATEMENT
        EXECUTE FUNCTION guard_aip9_content_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE FUNCTION guard_aip9_content_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'AIP9_CONTENT_APPEND_ONLY' USING ERRCODE='55000';
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE FUNCTION guard_aip9_content_event_sequence() RETURNS trigger AS $$
        DECLARE previous_sequence BIGINT; previous_kind TEXT;
        BEGIN
          IF TG_TABLE_NAME='aip_media_job_event' THEN
            SELECT sequence,event_kind INTO previous_sequence,previous_kind
            FROM aip_media_job_event
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id
              AND job_id=NEW.job_id
            ORDER BY sequence DESC LIMIT 1 FOR UPDATE;
            IF previous_kind IN ('succeeded','failed','cancelled') THEN
              RAISE EXCEPTION 'AIP9_MEDIA_EVENT_AFTER_TERMINAL' USING ERRCODE='23514';
            END IF;
          ELSE
            SELECT sequence,event_kind INTO previous_sequence,previous_kind
            FROM aip_avatar_session_event
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id
              AND session_id=NEW.session_id
            ORDER BY sequence DESC LIMIT 1 FOR UPDATE;
            IF previous_kind IN ('closed','failed','killed') THEN
              RAISE EXCEPTION 'AIP9_AVATAR_EVENT_AFTER_TERMINAL' USING ERRCODE='23514';
            END IF;
          END IF;
          IF previous_sequence IS NULL AND NEW.sequence <> 1 THEN
            RAISE EXCEPTION 'AIP9_CONTENT_EVENT_SEQUENCE' USING ERRCODE='23514';
          ELSIF previous_sequence IS NOT NULL
            AND NEW.sequence <> previous_sequence + 1 THEN
            RAISE EXCEPTION 'AIP9_CONTENT_EVENT_SEQUENCE' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql"""
    )

    op.execute(
        """CREATE TABLE aip_media_job (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, job_id TEXT NOT NULL,
          task_run_id TEXT NOT NULL, step_run_id TEXT NOT NULL,
          job_kind TEXT NOT NULL, request_json JSONB NOT NULL,
          request_hash TEXT NOT NULL, idempotency_key TEXT NOT NULL,
          attempt INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'queued',
          latest_sequence BIGINT NOT NULL DEFAULT 1, version BIGINT NOT NULL DEFAULT 1,
          executor_lease_ref JSONB, heartbeat_at TIMESTAMPTZ,
          lease_expires_at TIMESTAMPTZ, output_artifact_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          completion_receipt_ref JSONB, blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
          reason_code TEXT, deadline_at TIMESTAMPTZ NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ,
          PRIMARY KEY(org_id,project_id,job_id),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(job_kind IN ('tts','subtitle','video_render','transcode','thumbnail')),
          CHECK(status IN ('queued','running','succeeded','failed','cancelled','unknown')),
          CHECK(length(request_hash)=64), CHECK(attempt>=1),
          CHECK(latest_sequence>=1), CHECK(version>=1),
          CHECK(jsonb_typeof(request_json)='object'),
          CHECK(jsonb_typeof(output_artifact_refs)='array'),
          CHECK(jsonb_typeof(blockers)='array'),
          CHECK((status='running' AND executor_lease_ref IS NOT NULL
                 AND heartbeat_at IS NOT NULL AND lease_expires_at>heartbeat_at)
             OR (status<>'running' AND executor_lease_ref IS NULL
                 AND heartbeat_at IS NULL AND lease_expires_at IS NULL)),
          CHECK((status='succeeded' AND jsonb_array_length(output_artifact_refs)>0
                 AND completion_receipt_ref IS NOT NULL AND finished_at IS NOT NULL
                 AND jsonb_array_length(blockers)=0 AND reason_code IS NULL)
             OR status<>'succeeded'),
          CHECK((status IN ('failed','cancelled') AND reason_code IS NOT NULL
                 AND completion_receipt_ref IS NOT NULL AND finished_at IS NOT NULL)
             OR status NOT IN ('failed','cancelled')),
          CHECK((status='unknown' AND jsonb_array_length(blockers)>0 AND finished_at IS NULL)
             OR status<>'unknown'),
          CHECK(status NOT IN ('queued','running') OR finished_at IS NULL),
          CHECK(updated_at>=created_at),
          FOREIGN KEY(org_id,project_id,task_run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY(org_id,project_id,step_run_id)
            REFERENCES aip_step_run(org_id,project_id,step_run_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_media_job_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          job_id TEXT NOT NULL, sequence BIGINT NOT NULL, event_kind TEXT NOT NULL,
          event_json JSONB NOT NULL, event_hash TEXT NOT NULL,
          actor TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,event_id),
          UNIQUE(org_id,project_id,job_id,sequence),
          CHECK(sequence>=1), CHECK(length(event_hash)=64),
          CHECK(jsonb_typeof(event_json)='object'),
          CHECK(event_kind IN ('created','claimed','heartbeat','succeeded','failed',
                               'cancelled','unknown','reconciled')),
          FOREIGN KEY(org_id,project_id,job_id)
            REFERENCES aip_media_job(org_id,project_id,job_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_media_job_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          job_id TEXT NOT NULL, operation TEXT NOT NULL, idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL, response_json JSONB NOT NULL,
          response_hash TEXT NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,receipt_id),
          UNIQUE(org_id,project_id,operation,idempotency_key),
          CHECK(operation IN ('submit','claim','heartbeat','complete','cancel','reconcile')),
          CHECK(length(request_hash)=64), CHECK(length(response_hash)=64),
          CHECK(jsonb_typeof(response_json)='object'),
          FOREIGN KEY(org_id,project_id,job_id)
            REFERENCES aip_media_job(org_id,project_id,job_id)
        )"""
    )

    op.execute(
        """CREATE TABLE aip_avatar_session (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, session_id TEXT NOT NULL,
          task_run_id TEXT NOT NULL, step_run_id TEXT NOT NULL,
          request_json JSONB NOT NULL, request_hash TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, capability_binding_ref JSONB NOT NULL,
          budget_ref JSONB NOT NULL, kill_policy_ref JSONB NOT NULL,
          max_duration_seconds INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'opening',
          latest_sequence BIGINT NOT NULL DEFAULT 1, version BIGINT NOT NULL DEFAULT 1,
          engine_session_ref JSONB, human_heartbeat_at TIMESTAMPTZ,
          human_heartbeat_expires_at TIMESTAMPTZ, completion_receipt_ref JSONB,
          blockers JSONB NOT NULL DEFAULT '[]'::jsonb, reason_code TEXT,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ,
          PRIMARY KEY(org_id,project_id,session_id),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(status IN ('opening','ready','live','paused','closing','closed',
                           'failed','killed','unknown')),
          CHECK(length(request_hash)=64), CHECK(max_duration_seconds BETWEEN 1 AND 21600),
          CHECK(latest_sequence>=1), CHECK(version>=1),
          CHECK(jsonb_typeof(request_json)='object'),
          CHECK(jsonb_typeof(capability_binding_ref)='object'),
          CHECK(jsonb_typeof(budget_ref)='object'),
          CHECK(jsonb_typeof(kill_policy_ref)='object'),
          CHECK(jsonb_typeof(blockers)='array'),
          CHECK((status='live' AND engine_session_ref IS NOT NULL
                 AND human_heartbeat_at IS NOT NULL
                 AND human_heartbeat_expires_at>human_heartbeat_at)
             OR (status<>'live' AND human_heartbeat_at IS NULL
                 AND human_heartbeat_expires_at IS NULL)),
          CHECK((status IN ('closed','failed','killed')
                 AND completion_receipt_ref IS NOT NULL AND finished_at IS NOT NULL)
             OR status NOT IN ('closed','failed','killed')),
          CHECK((status IN ('failed','killed') AND reason_code IS NOT NULL)
             OR status NOT IN ('failed','killed')),
          CHECK((status='unknown' AND jsonb_array_length(blockers)>0)
             OR status<>'unknown'),
          CHECK(status IN ('closed','failed','killed')
             OR (completion_receipt_ref IS NULL AND finished_at IS NULL)),
          CHECK(updated_at>=created_at),
          FOREIGN KEY(org_id,project_id,task_run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY(org_id,project_id,step_run_id)
            REFERENCES aip_step_run(org_id,project_id,step_run_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_avatar_session_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          session_id TEXT NOT NULL, sequence BIGINT NOT NULL, event_kind TEXT NOT NULL,
          event_json JSONB NOT NULL, event_hash TEXT NOT NULL,
          actor TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,event_id),
          UNIQUE(org_id,project_id,session_id,sequence),
          CHECK(sequence>=1), CHECK(length(event_hash)=64),
          CHECK(jsonb_typeof(event_json)='object'),
          CHECK(event_kind IN ('opened','ready','heartbeat','live','paused','resumed',
                               'closing','closed','failed','killed','unknown','reconciled')),
          FOREIGN KEY(org_id,project_id,session_id)
            REFERENCES aip_avatar_session(org_id,project_id,session_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_avatar_session_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          session_id TEXT NOT NULL, operation TEXT NOT NULL, idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL, response_json JSONB NOT NULL,
          response_hash TEXT NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,receipt_id),
          UNIQUE(org_id,project_id,operation,idempotency_key),
          CHECK(operation IN ('open','heartbeat','push','pause','resume','close',
                              'kill','reconcile')),
          CHECK(length(request_hash)=64), CHECK(length(response_hash)=64),
          CHECK(jsonb_typeof(response_json)='object'),
          FOREIGN KEY(org_id,project_id,session_id)
            REFERENCES aip_avatar_session(org_id,project_id,session_id)
        )"""
    )

    op.execute(
        """CREATE INDEX aip_media_job_runtime_idx
        ON aip_media_job(org_id,project_id,status,updated_at DESC,job_id)"""
    )
    op.execute(
        """CREATE INDEX aip_media_job_step_idx
        ON aip_media_job(org_id,project_id,task_run_id,step_run_id,created_at DESC)"""
    )
    op.execute(
        """CREATE INDEX aip_media_job_event_latest_idx
        ON aip_media_job_event(org_id,project_id,job_id,sequence DESC)"""
    )
    op.execute(
        """CREATE INDEX aip_avatar_session_runtime_idx
        ON aip_avatar_session(org_id,project_id,status,updated_at DESC,session_id)"""
    )
    op.execute(
        """CREATE INDEX aip_avatar_session_step_idx
        ON aip_avatar_session(org_id,project_id,task_run_id,step_run_id,created_at DESC)"""
    )
    op.execute(
        """CREATE INDEX aip_avatar_session_event_latest_idx
        ON aip_avatar_session_event(org_id,project_id,session_id,sequence DESC)"""
    )
    op.execute(
        "CREATE TRIGGER trg_aip_media_job_event_sequence BEFORE INSERT ON "
        "aip_media_job_event FOR EACH ROW EXECUTE FUNCTION guard_aip9_content_event_sequence()"
    )
    op.execute(
        "CREATE TRIGGER trg_aip_avatar_session_event_sequence BEFORE INSERT ON "
        "aip_avatar_session_event FOR EACH ROW EXECUTE FUNCTION guard_aip9_content_event_sequence()"
    )

    for table in TABLES:
        _tenant_scope(table)
    for table in ("aip_media_job", "aip_avatar_session"):
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime")
        op.execute(f"REVOKE DELETE,TRUNCATE ON {table} FROM aos_runtime")
    for table in APPEND_ONLY_TABLES:
        _append_only(table)
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")
        op.execute(f"REVOKE UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")


def downgrade() -> None:
    non_empty = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in TABLES)
    op.execute(
        f"""DO $$ BEGIN
          IF {non_empty} THEN
            RAISE EXCEPTION 'AIP9_CONTENT_DOWNGRADE_REQUIRES_EMPTY_TABLES'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_aip9_content_event_sequence() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_aip9_content_append_only() CASCADE")
