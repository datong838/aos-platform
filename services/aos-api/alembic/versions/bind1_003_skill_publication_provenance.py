"""Add exact provenance for governed published Skill revisions.

Revision ID: bind1_003
Revises: bind1_002
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "bind1_003"
down_revision: str | Sequence[str] | None = "bind1_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_skill_template_revision
        ADD COLUMN parent_ref JSONB,
        ADD COLUMN publication_tenant JSONB,
        ADD COLUMN release_gate_ref JSONB,
        ADD COLUMN publication_ref JSONB,
        ADD COLUMN model_route_ref JSONB,
        ADD COLUMN runtime_policy_ref JSONB,
        ADD CONSTRAINT aip_skill_publication_provenance_chk CHECK (
          (lifecycle='published'
           AND parent_ref IS NOT NULL
           AND publication_tenant IS NOT NULL
           AND release_gate_ref IS NOT NULL
           AND publication_ref IS NOT NULL
           AND model_route_ref IS NOT NULL
           AND runtime_policy_ref IS NOT NULL)
          OR
          (lifecycle<>'published'
           AND parent_ref IS NULL
           AND publication_tenant IS NULL
           AND release_gate_ref IS NULL
           AND publication_ref IS NULL
           AND model_route_ref IS NULL
           AND runtime_policy_ref IS NULL)),
        ADD CONSTRAINT aip_skill_parent_ref_chk CHECK (
          parent_ref IS NULL OR (jsonb_typeof(parent_ref)='object'
            AND parent_ref->>'assetType'='SkillTemplate')),
        ADD CONSTRAINT aip_skill_publication_tenant_chk CHECK (
          publication_tenant IS NULL OR (jsonb_typeof(publication_tenant)='object'
            AND NULLIF(publication_tenant->>'orgId','') IS NOT NULL
            AND NULLIF(publication_tenant->>'projectId','') IS NOT NULL)),
        ADD CONSTRAINT aip_skill_release_gate_ref_chk CHECK (
          release_gate_ref IS NULL OR (jsonb_typeof(release_gate_ref)='object'
            AND release_gate_ref->>'assetType'='EvalGateDecision')),
        ADD CONSTRAINT aip_skill_publication_ref_chk CHECK (
          publication_ref IS NULL OR (jsonb_typeof(publication_ref)='object'
            AND publication_ref->>'resourceType'='PublicationEvent')),
        ADD CONSTRAINT aip_skill_publication_route_ref_chk CHECK (
          model_route_ref IS NULL OR (jsonb_typeof(model_route_ref)='object'
            AND model_route_ref->>'assetType'='ModelRouteRevision')),
        ADD CONSTRAINT aip_skill_publication_policy_ref_chk CHECK (
          runtime_policy_ref IS NULL OR (jsonb_typeof(runtime_policy_ref)='object'
            AND runtime_policy_ref->>'assetType'='RuntimePolicyRevision'))"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM aip_skill_template_revision
            WHERE lifecycle='published'
               OR parent_ref IS NOT NULL
               OR publication_ref IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'BIND1_003_DOWNGRADE_REQUIRES_NO_PUBLISHED_SKILLS'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    op.execute(
        """ALTER TABLE aip_skill_template_revision
        DROP CONSTRAINT aip_skill_publication_policy_ref_chk,
        DROP CONSTRAINT aip_skill_publication_route_ref_chk,
        DROP CONSTRAINT aip_skill_publication_ref_chk,
        DROP CONSTRAINT aip_skill_release_gate_ref_chk,
        DROP CONSTRAINT aip_skill_publication_tenant_chk,
        DROP CONSTRAINT aip_skill_parent_ref_chk,
        DROP CONSTRAINT aip_skill_publication_provenance_chk,
        DROP COLUMN runtime_policy_ref,
        DROP COLUMN model_route_ref,
        DROP COLUMN publication_ref,
        DROP COLUMN release_gate_ref,
        DROP COLUMN publication_tenant,
        DROP COLUMN parent_ref"""
    )
