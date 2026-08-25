"""Profile projected cost and governed confirmation envelope (W7-02).

Revision ID: w7_001
Revises: w6_009
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w7_001"
down_revision: str | Sequence[str] | None = "w6_009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE aip_profile_recommendation_revision
          ADD COLUMN dependency_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN projected_cost_ranges JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN projected_duration JSONB,
          ADD COLUMN assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN confidence TEXT NOT NULL DEFAULT 'unknown',
          ADD COLUMN readiness TEXT NOT NULL DEFAULT 'unknown',
          ADD COLUMN blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD CONSTRAINT ck_profile_recommendation_dependencies_array
            CHECK (jsonb_typeof(dependency_refs)='array'),
          ADD CONSTRAINT ck_profile_recommendation_cost_ranges_array
            CHECK (jsonb_typeof(projected_cost_ranges)='array'),
          ADD CONSTRAINT ck_profile_recommendation_duration_object
            CHECK (projected_duration IS NULL OR jsonb_typeof(projected_duration)='object'),
          ADD CONSTRAINT ck_profile_recommendation_assumptions_array
            CHECK (jsonb_typeof(assumptions)='array'),
          ADD CONSTRAINT ck_profile_recommendation_confidence
            CHECK (confidence IN ('high','medium','low','unknown')),
          ADD CONSTRAINT ck_profile_recommendation_readiness
            CHECK (readiness IN ('ready','blocked','stale','unknown')),
          ADD CONSTRAINT ck_profile_recommendation_blockers_array
            CHECK (jsonb_typeof(blockers)='array');

        ALTER TABLE aip_profile_confirmation_receipt
          ADD COLUMN recommendation_etag CHAR(64),
          ADD COLUMN idempotency_key TEXT,
          ADD COLUMN command_hash CHAR(64),
          ADD COLUMN selected_projected_cost_ranges JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD CONSTRAINT ck_profile_confirmation_etag
            CHECK (recommendation_etag IS NULL OR recommendation_etag ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT ck_profile_confirmation_command_hash
            CHECK (command_hash IS NULL OR command_hash ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT ck_profile_confirmation_cost_ranges_array
            CHECK (jsonb_typeof(selected_projected_cost_ranges)='array'),
          ADD CONSTRAINT uq_profile_confirmation_idempotency
            UNIQUE (org_id,project_id,idempotency_key);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE aip_profile_confirmation_receipt
          DROP CONSTRAINT IF EXISTS uq_profile_confirmation_idempotency,
          DROP CONSTRAINT IF EXISTS ck_profile_confirmation_cost_ranges_array,
          DROP CONSTRAINT IF EXISTS ck_profile_confirmation_command_hash,
          DROP CONSTRAINT IF EXISTS ck_profile_confirmation_etag,
          DROP COLUMN IF EXISTS selected_projected_cost_ranges,
          DROP COLUMN IF EXISTS command_hash,
          DROP COLUMN IF EXISTS idempotency_key,
          DROP COLUMN IF EXISTS recommendation_etag;

        ALTER TABLE aip_profile_recommendation_revision
          DROP CONSTRAINT IF EXISTS ck_profile_recommendation_blockers_array,
          DROP CONSTRAINT IF EXISTS ck_profile_recommendation_readiness,
          DROP CONSTRAINT IF EXISTS ck_profile_recommendation_confidence,
          DROP CONSTRAINT IF EXISTS ck_profile_recommendation_assumptions_array,
          DROP CONSTRAINT IF EXISTS ck_profile_recommendation_duration_object,
          DROP CONSTRAINT IF EXISTS ck_profile_recommendation_cost_ranges_array,
          DROP CONSTRAINT IF EXISTS ck_profile_recommendation_dependencies_array,
          DROP COLUMN IF EXISTS blockers,
          DROP COLUMN IF EXISTS readiness,
          DROP COLUMN IF EXISTS confidence,
          DROP COLUMN IF EXISTS assumptions,
          DROP COLUMN IF EXISTS projected_duration,
          DROP COLUMN IF EXISTS projected_cost_ranges,
          DROP COLUMN IF EXISTS dependency_refs;
        """
    )
