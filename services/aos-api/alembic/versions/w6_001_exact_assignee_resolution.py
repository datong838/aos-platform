"""Exact assignee candidate and readiness snapshots (W6-01).

Revision ID: w6_001
Revises: w5_006
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w6_001"
down_revision: str | Sequence[str] | None = "w5_006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_tool_binding
           ADD COLUMN capability_binding_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
           ADD COLUMN policy_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
           ADD CONSTRAINT ck_aip_tool_binding_capability_binding_ids_array
             CHECK (jsonb_typeof(capability_binding_ids)='array'),
           ADD CONSTRAINT ck_aip_tool_binding_policy_refs_array
             CHECK (jsonb_typeof(policy_refs)='array')"""
    )
    op.execute(
        """ALTER TABLE aip_assignee_resolution_receipt
           ADD COLUMN selected_assignee JSONB,
           ADD COLUMN required_capability_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
           ADD COLUMN candidate_decisions JSONB NOT NULL DEFAULT '[]'::jsonb,
           ADD COLUMN binding_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
           ADD COLUMN policy_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
           ADD COLUMN snapshot_hash CHAR(64),
           ADD COLUMN expires_at TIMESTAMPTZ,
           ADD CONSTRAINT ck_aip_assignee_selected_assignee_object
             CHECK (selected_assignee IS NULL OR jsonb_typeof(selected_assignee)='object'),
           ADD CONSTRAINT ck_aip_assignee_required_capabilities_array
             CHECK (jsonb_typeof(required_capability_refs)='array'),
           ADD CONSTRAINT ck_aip_assignee_candidate_decisions_array
             CHECK (jsonb_typeof(candidate_decisions)='array'),
           ADD CONSTRAINT ck_aip_assignee_binding_refs_array
             CHECK (jsonb_typeof(binding_refs)='array'),
           ADD CONSTRAINT ck_aip_assignee_policy_refs_array
             CHECK (jsonb_typeof(policy_refs)='array'),
           ADD CONSTRAINT ck_aip_assignee_snapshot_hash
             CHECK (snapshot_hash IS NULL OR snapshot_hash ~ '^[0-9a-f]{64}$'),
           ADD CONSTRAINT ck_aip_assignee_freshness_window
             CHECK (expires_at IS NULL OR expires_at > created_at)"""
    )


def downgrade() -> None:
    op.execute(
        """ALTER TABLE aip_assignee_resolution_receipt
           DROP CONSTRAINT IF EXISTS ck_aip_assignee_freshness_window,
           DROP CONSTRAINT IF EXISTS ck_aip_assignee_snapshot_hash,
           DROP CONSTRAINT IF EXISTS ck_aip_assignee_policy_refs_array,
           DROP CONSTRAINT IF EXISTS ck_aip_assignee_binding_refs_array,
           DROP CONSTRAINT IF EXISTS ck_aip_assignee_candidate_decisions_array,
           DROP CONSTRAINT IF EXISTS ck_aip_assignee_required_capabilities_array,
           DROP CONSTRAINT IF EXISTS ck_aip_assignee_selected_assignee_object,
           DROP COLUMN IF EXISTS expires_at,
           DROP COLUMN IF EXISTS snapshot_hash,
           DROP COLUMN IF EXISTS policy_refs,
           DROP COLUMN IF EXISTS binding_refs,
           DROP COLUMN IF EXISTS candidate_decisions,
           DROP COLUMN IF EXISTS required_capability_refs,
           DROP COLUMN IF EXISTS selected_assignee"""
    )
    op.execute(
        """ALTER TABLE aip_tool_binding
           DROP CONSTRAINT IF EXISTS ck_aip_tool_binding_policy_refs_array,
           DROP CONSTRAINT IF EXISTS ck_aip_tool_binding_capability_binding_ids_array,
           DROP COLUMN IF EXISTS policy_refs,
           DROP COLUMN IF EXISTS capability_binding_ids"""
    )
