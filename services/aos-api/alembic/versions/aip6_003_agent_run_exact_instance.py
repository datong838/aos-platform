"""Persist exact AgentInstance snapshots on AgentRun and Handoff.

Revision ID: aip6_003
Revises: aip6_002
Create Date: 2026-08-13
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip6_003"
down_revision: str | Sequence[str] | None = "aip6_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE aip_agent_run ADD COLUMN task_ref JSONB")
    op.execute("ALTER TABLE aip_agent_run ADD COLUMN task_run_ref JSONB")
    op.execute("ALTER TABLE aip_agent_run ADD COLUMN instance_ref JSONB")
    op.execute("ALTER TABLE aip_agent_run ADD COLUMN instance_snapshot JSONB")
    op.execute(
        """UPDATE aip_agent_run r SET
          task_ref=jsonb_build_object('resourceType','Task','resourceId',r.task_id,
            'revision',NULL,'authority','aip-task-runtime'),
          task_run_ref=jsonb_build_object('resourceType','TaskRun','resourceId',r.task_run_id,
            'revision',NULL,'authority','aip-task-runtime')
        WHERE task_ref IS NULL OR task_run_ref IS NULL"""
    )
    op.execute(
        """UPDATE aip_agent_run r SET instance_ref=jsonb_build_object(
          'assetType','AgentInstance','assetId',r.instance_id,
          'revision',r.instance_version,'contentHash',repeat('0',64))
        WHERE instance_ref IS NULL"""
    )
    op.execute(
        """UPDATE aip_agent_run SET instance_snapshot=jsonb_build_object(
          'instanceId',instance_id,'version',instance_version,'legacy',true)
        WHERE instance_snapshot IS NULL"""
    )
    op.execute("ALTER TABLE aip_agent_run ALTER COLUMN instance_ref SET NOT NULL")
    op.execute("ALTER TABLE aip_agent_run ALTER COLUMN instance_snapshot SET NOT NULL")
    op.execute("ALTER TABLE aip_agent_run ALTER COLUMN task_ref SET NOT NULL")
    op.execute("ALTER TABLE aip_agent_run ALTER COLUMN task_run_ref SET NOT NULL")
    op.execute(
        "ALTER TABLE aip_agent_run ADD CONSTRAINT ck_aip_agent_run_instance_ref "
        "CHECK (jsonb_typeof(instance_ref)='object')"
    )
    op.execute(
        "ALTER TABLE aip_agent_run ADD CONSTRAINT ck_aip_agent_run_instance_snapshot "
        "CHECK (jsonb_typeof(instance_snapshot)='object')"
    )
    op.execute(
        "ALTER TABLE aip_agent_run ADD CONSTRAINT ck_aip_agent_run_task_refs "
        "CHECK (jsonb_typeof(task_ref)='object' AND jsonb_typeof(task_run_ref)='object')"
    )
    op.execute("ALTER TABLE aip_handoff_envelope ADD COLUMN task_ref JSONB")
    op.execute("ALTER TABLE aip_handoff_envelope ADD COLUMN task_run_ref JSONB")
    op.execute("ALTER TABLE aip_handoff_envelope ADD COLUMN sender_instance_ref JSONB")
    op.execute("ALTER TABLE aip_handoff_envelope ADD COLUMN receiver_instance_ref JSONB")
    op.execute(
        """UPDATE aip_handoff_envelope SET
          task_ref=jsonb_build_object('resourceType','Task','resourceId',task_id,
            'revision',NULL,'authority','aip-task-runtime'),
          task_run_ref=jsonb_build_object('resourceType','TaskRun','resourceId',task_run_id,
            'revision',NULL,'authority','aip-task-runtime'),
          sender_instance_ref=jsonb_build_object('assetType','AgentInstance',
            'assetId',sender_instance_id,'revision',1,'contentHash',repeat('0',64)),
          receiver_instance_ref=jsonb_build_object('assetType','AgentInstance',
            'assetId',receiver_instance_id,'revision',1,'contentHash',repeat('0',64))
        WHERE sender_instance_ref IS NULL OR receiver_instance_ref IS NULL"""
    )
    op.execute("ALTER TABLE aip_handoff_envelope ALTER COLUMN sender_instance_ref SET NOT NULL")
    op.execute("ALTER TABLE aip_handoff_envelope ALTER COLUMN receiver_instance_ref SET NOT NULL")
    op.execute("ALTER TABLE aip_handoff_envelope ALTER COLUMN task_ref SET NOT NULL")
    op.execute("ALTER TABLE aip_handoff_envelope ALTER COLUMN task_run_ref SET NOT NULL")
    op.execute(
        "ALTER TABLE aip_handoff_envelope ADD CONSTRAINT ck_aip_handoff_sender_instance_ref "
        "CHECK (jsonb_typeof(sender_instance_ref)='object')"
    )
    op.execute(
        "ALTER TABLE aip_handoff_envelope ADD CONSTRAINT ck_aip_handoff_receiver_instance_ref "
        "CHECK (jsonb_typeof(receiver_instance_ref)='object')"
    )
    op.execute(
        "ALTER TABLE aip_handoff_envelope ADD CONSTRAINT ck_aip_handoff_task_refs "
        "CHECK (jsonb_typeof(task_ref)='object' AND jsonb_typeof(task_run_ref)='object')"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE aip_handoff_envelope DROP COLUMN IF EXISTS task_run_ref")
    op.execute("ALTER TABLE aip_handoff_envelope DROP COLUMN IF EXISTS task_ref")
    op.execute("ALTER TABLE aip_handoff_envelope DROP COLUMN IF EXISTS receiver_instance_ref")
    op.execute("ALTER TABLE aip_handoff_envelope DROP COLUMN IF EXISTS sender_instance_ref")
    op.execute("ALTER TABLE aip_agent_run DROP COLUMN IF EXISTS instance_snapshot")
    op.execute("ALTER TABLE aip_agent_run DROP COLUMN IF EXISTS instance_ref")
    op.execute("ALTER TABLE aip_agent_run DROP COLUMN IF EXISTS task_run_ref")
    op.execute("ALTER TABLE aip_agent_run DROP COLUMN IF EXISTS task_ref")
