"""Adopt meta_schedule_run into the managed tenant schema.

Revision ID: a0v_001
Revises: ar2_018
Create Date: 2026-09-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "a0v_001"
down_revision: str | Sequence[str] | None = "ar2_018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "meta_schedule_run"
POLICY = "tenant_scope_meta_schedule_run_a0v001"


def upgrade() -> None:
    # The table used to be created only by application bootstrap.  Validate an
    # adopted legacy table before adding managed security; never bless drift.
    op.execute(
        r"""
        DO $$
        DECLARE actual_shape text;
        BEGIN
          IF to_regclass('public.meta_schedule_run') IS NOT NULL THEN
            SELECT string_agg(
                     a.attname::text || ':' || pg_catalog.format_type(a.atttypid,a.atttypmod)
                       || ':' || a.attnotnull::text,
                     ',' ORDER BY a.attnum)
              INTO actual_shape
              FROM pg_catalog.pg_attribute a
             WHERE a.attrelid='public.meta_schedule_run'::regclass
               AND a.attnum>0 AND NOT a.attisdropped;
            IF actual_shape IS DISTINCT FROM
              'id:text:true,org_id:text:true,project_id:text:true,'
              'schedule_id:text:true,scheduled_for:timestamp with time zone:true,'
              'trigger:text:true,status:text:true,'
              'started_at:timestamp with time zone:true,'
              'finished_at:timestamp with time zone:false,'
              'duration_ms:integer:true,rows_written:integer:true,'
              'error_code:text:true,error_message:text:true,executor_id:text:true'
            THEN
              RAISE EXCEPTION 'meta_schedule_run schema drift blocks managed adoption'
                USING ERRCODE='55000';
            END IF;
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_schedule_run (
          id TEXT NOT NULL,
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          schedule_id TEXT NOT NULL,
          scheduled_for TIMESTAMPTZ NOT NULL,
          trigger TEXT NOT NULL,
          status TEXT NOT NULL,
          started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          finished_at TIMESTAMPTZ,
          duration_ms INTEGER NOT NULL DEFAULT 0,
          rows_written INTEGER NOT NULL DEFAULT 0,
          error_code TEXT NOT NULL DEFAULT '',
          error_message TEXT NOT NULL DEFAULT '',
          executor_id TEXT NOT NULL DEFAULT '',
          PRIMARY KEY (org_id, project_id, schedule_id, scheduled_for),
          UNIQUE (org_id, project_id, id)
        )
        """
    )
    op.execute(
        r"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_constraint c
             WHERE c.conrelid='public.meta_schedule_run'::regclass
               AND c.contype='p'
               AND ARRAY(
                 SELECT a.attname::text
                   FROM unnest(c.conkey) WITH ORDINALITY AS key(attnum,position)
                   JOIN pg_catalog.pg_attribute a
                     ON a.attrelid=c.conrelid AND a.attnum=key.attnum
                  ORDER BY key.position
               )=ARRAY['org_id','project_id','schedule_id','scheduled_for']
          ) OR NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_constraint c
             WHERE c.conrelid='public.meta_schedule_run'::regclass
               AND c.contype='u'
               AND ARRAY(
                 SELECT a.attname::text
                   FROM unnest(c.conkey) WITH ORDINALITY AS key(attnum,position)
                   JOIN pg_catalog.pg_attribute a
                     ON a.attrelid=c.conrelid AND a.attnum=key.attnum
                  ORDER BY key.position
               )=ARRAY['org_id','project_id','id']
          ) THEN
            RAISE EXCEPTION 'meta_schedule_run key contract blocks managed adoption'
              USING ERRCODE='55000';
          END IF;
          IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname='public' AND tablename='meta_schedule_run'
               AND policyname<>'tenant_scope_meta_schedule_run_a0v001'
          ) THEN
            RAISE EXCEPTION 'meta_schedule_run unknown policy blocks managed adoption'
              USING ERRCODE='55000';
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_meta_schedule_run_history
          ON meta_schedule_run (org_id, project_id, schedule_id, started_at DESC)
        """
    )
    op.execute(
        r"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_indexes
             WHERE schemaname='public' AND tablename='meta_schedule_run'
               AND indexname='idx_meta_schedule_run_history'
               AND indexdef LIKE '%(org_id, project_id, schedule_id, started_at DESC)'
          ) THEN
            RAISE EXCEPTION 'meta_schedule_run history index drift blocks managed adoption'
              USING ERRCODE='55000';
          END IF;
        END $$;
        """
    )
    op.execute(f"DROP POLICY IF EXISTS {POLICY} ON {TABLE}")
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {POLICY} ON {TABLE} FOR ALL TO aos_runtime
          USING (
            org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),'')
          )
          WITH CHECK (
            org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),'')
          )
        """
    )
    op.execute(f"REVOKE ALL ON {TABLE} FROM PUBLIC,aos_runtime")
    op.execute(f"GRANT SELECT,INSERT,UPDATE ON {TABLE} TO aos_runtime")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM meta_schedule_run LIMIT 1) THEN
            RAISE EXCEPTION 'meta_schedule_run downgrade blocked: run history exists'
              USING ERRCODE='55000';
          END IF;
        END $$
        """
    )
    op.execute("DROP TABLE meta_schedule_run")
