"""Align BIND provider refs with the AIP-7 ProviderInstance authority.

Revision ID: bind1_002
Revises: bind1_001
Create Date: 2026-08-15
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "bind1_002"
down_revision: str | Sequence[str] | None = "bind1_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_capability_binding
        DROP CONSTRAINT aip_capability_binding_provider_ref_chk,
        ADD CONSTRAINT aip_capability_binding_provider_ref_chk CHECK (
          provider_ref IS NULL OR (jsonb_typeof(provider_ref)='object'
            AND provider_ref->>'assetType'='ProviderInstanceRevision'))"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM aip_capability_binding
            WHERE provider_ref IS NOT NULL
              AND provider_ref->>'assetType' <> 'ProviderRevision'
          ) THEN
            RAISE EXCEPTION 'BIND1_PROVIDER_REF_DOWNGRADE_REQUIRES_NO_INSTANCE_REFS'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    op.execute(
        """ALTER TABLE aip_capability_binding
        DROP CONSTRAINT aip_capability_binding_provider_ref_chk,
        ADD CONSTRAINT aip_capability_binding_provider_ref_chk CHECK (
          provider_ref IS NULL OR (jsonb_typeof(provider_ref)='object'
            AND provider_ref->>'assetType'='ProviderRevision'))"""
    )
