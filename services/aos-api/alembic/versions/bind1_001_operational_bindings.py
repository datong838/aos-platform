"""Add BIND-1 operational dependency snapshots to existing bindings.

Revision ID: bind1_001
Revises: aip5_005
Create Date: 2026-08-15
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "bind1_001"
down_revision: str | Sequence[str] | None = "aip5_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_capability_binding
        ADD COLUMN provider_ref JSONB,
        ADD COLUMN model_route_ref JSONB,
        ADD COLUMN runtime_policy_ref JSONB,
        ADD COLUMN eval_gate_ref JSONB,
        ADD COLUMN eval_contract_ref JSONB,
        ADD COLUMN license_evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN data_dependency_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN tool_dependency_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN budget_policy_ref JSONB,
        ADD COLUMN allow_degraded BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN dependency_snapshot_hash TEXT,
        ADD COLUMN operational_readiness TEXT NOT NULL DEFAULT 'unknown',
        ADD COLUMN readiness_reasons JSONB NOT NULL
          DEFAULT '["BINDING_NOT_EVALUATED"]'::jsonb,
        ADD COLUMN last_evaluated_at TIMESTAMPTZ,
        ADD COLUMN readiness_expires_at TIMESTAMPTZ,
        ADD CONSTRAINT aip_capability_binding_operational_readiness_chk
          CHECK (operational_readiness IN
            ('available','degraded','disabled','blocked','unknown')),
        ADD CONSTRAINT aip_capability_binding_dependencies_json_chk CHECK (
          jsonb_typeof(license_evidence_refs)='array'
          AND jsonb_typeof(data_dependency_refs)='array'
          AND jsonb_typeof(tool_dependency_refs)='array'
          AND jsonb_typeof(readiness_reasons)='array'),
        ADD CONSTRAINT aip_capability_binding_snapshot_hash_chk CHECK (
          dependency_snapshot_hash IS NULL
          OR dependency_snapshot_hash ~ '^[0-9a-f]{64}$'),
        ADD CONSTRAINT aip_capability_binding_readiness_expiry_chk CHECK (
          readiness_expires_at IS NULL OR last_evaluated_at IS NOT NULL),
        ADD CONSTRAINT aip_capability_binding_provider_ref_chk CHECK (
          provider_ref IS NULL OR (jsonb_typeof(provider_ref)='object'
            AND provider_ref->>'assetType'='ProviderRevision')),
        ADD CONSTRAINT aip_capability_binding_route_ref_chk CHECK (
          model_route_ref IS NULL OR (jsonb_typeof(model_route_ref)='object'
            AND model_route_ref->>'assetType'='ModelRouteRevision')),
        ADD CONSTRAINT aip_capability_binding_runtime_policy_ref_chk CHECK (
          runtime_policy_ref IS NULL OR (jsonb_typeof(runtime_policy_ref)='object'
            AND runtime_policy_ref->>'assetType'='RuntimePolicyRevision')),
        ADD CONSTRAINT aip_capability_binding_eval_gate_ref_chk CHECK (
          eval_gate_ref IS NULL OR (jsonb_typeof(eval_gate_ref)='object'
            AND eval_gate_ref->>'assetType'='EvalGateDecision')),
        ADD CONSTRAINT aip_capability_binding_eval_contract_ref_chk CHECK (
          eval_contract_ref IS NULL OR (jsonb_typeof(eval_contract_ref)='object'
            AND eval_contract_ref->>'assetType'='EvalContractRevision')),
        ADD CONSTRAINT aip_capability_binding_budget_policy_ref_chk CHECK (
          budget_policy_ref IS NULL OR (jsonb_typeof(budget_policy_ref)='object'
            AND budget_policy_ref->>'assetType'='BudgetPolicyRevision'))"""
    )
    op.execute(
        """CREATE INDEX aip_capability_binding_readiness_idx
        ON aip_capability_binding(
          org_id,project_id,operational_readiness,status,updated_at DESC)"""
    )
    op.execute(
        """ALTER TABLE aip_skill_binding
        ADD COLUMN model_route_ref JSONB,
        ADD COLUMN runtime_policy_ref JSONB,
        ADD COLUMN eval_gate_ref JSONB,
        ADD COLUMN dependency_snapshot_hash TEXT,
        ADD COLUMN readiness TEXT NOT NULL DEFAULT 'unknown',
        ADD COLUMN readiness_reasons JSONB NOT NULL
          DEFAULT '["BINDING_NOT_EVALUATED"]'::jsonb,
        ADD COLUMN last_evaluated_at TIMESTAMPTZ,
        ADD COLUMN readiness_expires_at TIMESTAMPTZ,
        ADD CONSTRAINT aip_skill_binding_readiness_chk CHECK (
          readiness IN ('available','degraded','disabled','blocked','unknown')),
        ADD CONSTRAINT aip_skill_binding_readiness_reasons_chk CHECK (
          jsonb_typeof(readiness_reasons)='array'),
        ADD CONSTRAINT aip_skill_binding_snapshot_hash_chk CHECK (
          dependency_snapshot_hash IS NULL
          OR dependency_snapshot_hash ~ '^[0-9a-f]{64}$'),
        ADD CONSTRAINT aip_skill_binding_readiness_expiry_chk CHECK (
          readiness_expires_at IS NULL OR last_evaluated_at IS NOT NULL),
        ADD CONSTRAINT aip_skill_binding_route_ref_chk CHECK (
          model_route_ref IS NULL OR (jsonb_typeof(model_route_ref)='object'
            AND model_route_ref->>'assetType'='ModelRouteRevision')),
        ADD CONSTRAINT aip_skill_binding_runtime_policy_ref_chk CHECK (
          runtime_policy_ref IS NULL OR (jsonb_typeof(runtime_policy_ref)='object'
            AND runtime_policy_ref->>'assetType'='RuntimePolicyRevision')),
        ADD CONSTRAINT aip_skill_binding_eval_gate_ref_chk CHECK (
          eval_gate_ref IS NULL OR (jsonb_typeof(eval_gate_ref)='object'
            AND eval_gate_ref->>'assetType'='EvalGateDecision'))"""
    )
    op.execute(
        """CREATE INDEX aip_skill_binding_readiness_idx
        ON aip_skill_binding(
          org_id,project_id,readiness,status,updated_at DESC)"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM aip_capability_binding LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_skill_binding LIMIT 1) THEN
            RAISE EXCEPTION 'BIND1_DOWNGRADE_REQUIRES_EMPTY_BINDINGS'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    op.execute("DROP INDEX IF EXISTS aip_skill_binding_readiness_idx")
    op.execute(
        """ALTER TABLE aip_skill_binding
        DROP COLUMN readiness_expires_at,
        DROP COLUMN last_evaluated_at,
        DROP COLUMN readiness_reasons,
        DROP COLUMN readiness,
        DROP COLUMN dependency_snapshot_hash,
        DROP COLUMN eval_gate_ref,
        DROP COLUMN runtime_policy_ref,
        DROP COLUMN model_route_ref"""
    )
    op.execute("DROP INDEX IF EXISTS aip_capability_binding_readiness_idx")
    op.execute(
        """ALTER TABLE aip_capability_binding
        DROP COLUMN readiness_expires_at,
        DROP COLUMN last_evaluated_at,
        DROP COLUMN readiness_reasons,
        DROP COLUMN operational_readiness,
        DROP COLUMN dependency_snapshot_hash,
        DROP COLUMN allow_degraded,
        DROP COLUMN budget_policy_ref,
        DROP COLUMN tool_dependency_refs,
        DROP COLUMN data_dependency_refs,
        DROP COLUMN license_evidence_refs,
        DROP COLUMN eval_contract_ref,
        DROP COLUMN eval_gate_ref,
        DROP COLUMN runtime_policy_ref,
        DROP COLUMN model_route_ref,
        DROP COLUMN provider_ref"""
    )
