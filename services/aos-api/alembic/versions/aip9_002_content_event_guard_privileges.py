"""Run AIP-9 event sequence locking through a fixed-path definer guard.

Revision ID: aip9_002
Revises: aip9_001
Create Date: 2026-08-16
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip9_002"
down_revision: str | Sequence[str] | None = "aip9_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_BODY = """RETURNS trigger AS $$
DECLARE previous_sequence BIGINT; previous_kind TEXT; previous_status TEXT;
BEGIN
  IF TG_TABLE_NAME='aip_media_job_event' THEN
    SELECT sequence,event_kind,event_json->>'status'
      INTO previous_sequence,previous_kind,previous_status
    FROM public.aip_media_job_event
    WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND job_id=NEW.job_id
    ORDER BY sequence DESC LIMIT 1 FOR UPDATE;
    IF previous_kind IN ('succeeded','failed','cancelled')
       OR previous_status IN ('succeeded','failed','cancelled') THEN
      RAISE EXCEPTION 'AIP9_MEDIA_EVENT_AFTER_TERMINAL' USING ERRCODE='23514';
    END IF;
  ELSE
    SELECT sequence,event_kind,event_json->>'status'
      INTO previous_sequence,previous_kind,previous_status
    FROM public.aip_avatar_session_event
    WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND session_id=NEW.session_id
    ORDER BY sequence DESC LIMIT 1 FOR UPDATE;
    IF previous_kind IN ('closed','failed','killed')
       OR previous_status IN ('closed','failed','killed') THEN
      RAISE EXCEPTION 'AIP9_AVATAR_EVENT_AFTER_TERMINAL' USING ERRCODE='23514';
    END IF;
  END IF;
  IF previous_sequence IS NULL AND NEW.sequence <> 1 THEN
    RAISE EXCEPTION 'AIP9_CONTENT_EVENT_SEQUENCE' USING ERRCODE='23514';
  ELSIF previous_sequence IS NOT NULL AND NEW.sequence <> previous_sequence + 1 THEN
    RAISE EXCEPTION 'AIP9_CONTENT_EVENT_SEQUENCE' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql"""


def upgrade() -> None:
    op.execute(
        "CREATE OR REPLACE FUNCTION guard_aip9_content_event_sequence() "
        + _BODY
        + " SECURITY DEFINER SET search_path = pg_catalog, public"
    )
    op.execute("REVOKE ALL ON FUNCTION guard_aip9_content_event_sequence() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION guard_aip9_content_event_sequence() TO aos_runtime")
    op.execute(
        """ALTER TABLE aip_media_job_receipt
        DROP CONSTRAINT aip_media_job_receipt_operation_check,
        ADD CONSTRAINT aip_media_job_receipt_operation_check CHECK (
          operation IN ('submit','claim','heartbeat','succeed','fail','cancel',
                        'mark_unknown','reconcile'))"""
    )
    op.execute(
        """ALTER TABLE aip_avatar_session_receipt
        DROP CONSTRAINT aip_avatar_session_receipt_operation_check,
        ADD CONSTRAINT aip_avatar_session_receipt_operation_check CHECK (
          operation IN ('open','ready','live','heartbeat','push','pause','resume',
                        'closing','close','fail','kill','mark_unknown','reconcile'))"""
    )


def downgrade() -> None:
    op.execute(
        """ALTER TABLE aip_avatar_session_receipt
        DROP CONSTRAINT aip_avatar_session_receipt_operation_check,
        ADD CONSTRAINT aip_avatar_session_receipt_operation_check CHECK (
          operation IN ('open','heartbeat','push','pause','resume','close','kill','reconcile'))"""
    )
    op.execute(
        """ALTER TABLE aip_media_job_receipt
        DROP CONSTRAINT aip_media_job_receipt_operation_check,
        ADD CONSTRAINT aip_media_job_receipt_operation_check CHECK (
          operation IN ('submit','claim','heartbeat','complete','cancel','reconcile'))"""
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION guard_aip9_content_event_sequence() "
        + _BODY
        + " SECURITY INVOKER"
    )
    op.execute("GRANT EXECUTE ON FUNCTION guard_aip9_content_event_sequence() TO PUBLIC")
