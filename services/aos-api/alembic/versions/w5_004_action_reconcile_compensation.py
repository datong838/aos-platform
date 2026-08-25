"""Add durable Action reconciliation and exact compensation policy facts.

Revision ID: w5_004
Revises: w5_003
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w5_004"
down_revision: str | Sequence[str] | None = "w5_003"
branch_labels = None
depends_on = None


def _scope(table: str, *, update: bool = False) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_w5_004 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT SELECT,INSERT{',UPDATE' if update else ''} ON {table} TO aos_runtime")


def upgrade() -> None:
    op.execute("ALTER TABLE aip_action_execution_attempt DROP CONSTRAINT IF EXISTS aip_action_execution_attempt_status_check")
    op.execute(
        """ALTER TABLE aip_action_execution_attempt
        ADD CONSTRAINT aip_action_execution_attempt_status_check
        CHECK (status IN ('prepared','dispatch_claimed','accepted','applied','failed','partial','unknown'))"""
    )
    op.execute(
        """CREATE TABLE aip_action_reconcile_attempt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          reconcile_attempt_id TEXT NOT NULL, original_receipt_id TEXT NOT NULL,
          attempt_id TEXT, proposal_id TEXT NOT NULL,
          adapter_revision_ref JSONB, account_binding_ref JSONB,
          provider_request_id TEXT, request_fingerprint TEXT NOT NULL,
          query_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
          status TEXT NOT NULL DEFAULT 'pending', claim_token TEXT,
          expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          claimed_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
          PRIMARY KEY (org_id,project_id,reconcile_attempt_id),
          UNIQUE (org_id,project_id,original_receipt_id),
          CHECK (status IN ('pending','claimed','resolved','manual_required')),
          FOREIGN KEY (org_id,project_id,original_receipt_id)
            REFERENCES aip_action_receipt(org_id,project_id,receipt_id),
          FOREIGN KEY (org_id,project_id,attempt_id)
            REFERENCES aip_action_execution_attempt(org_id,project_id,attempt_id),
          FOREIGN KEY (org_id,project_id,proposal_id)
            REFERENCES aip_action_proposal(org_id,project_id,proposal_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_manual_reconcile_case (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, case_id TEXT NOT NULL,
          original_receipt_id TEXT NOT NULL, reconcile_attempt_id TEXT,
          attempt_id TEXT, proposal_id TEXT NOT NULL, action_binding_hash TEXT,
          account_binding_ref JSONB, object_scope JSONB, expected_diff JSONB,
          required_facts JSONB NOT NULL DEFAULT '[]'::jsonb,
          evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          missing_facts JSONB NOT NULL DEFAULT '[]'::jsonb,
          conflict_facts JSONB NOT NULL DEFAULT '[]'::jsonb,
          maker_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
          version BIGINT NOT NULL DEFAULT 1, expires_at TIMESTAMPTZ NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,case_id),
          UNIQUE (org_id,project_id,original_receipt_id),
          CHECK (status IN ('open','unresolved','resolved')),
          CHECK (version >= 1),
          CHECK (action_binding_hash IS NULL OR action_binding_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(required_facts)='array' AND jsonb_typeof(evidence_refs)='array'
             AND jsonb_typeof(missing_facts)='array' AND jsonb_typeof(conflict_facts)='array'),
          FOREIGN KEY (org_id,project_id,original_receipt_id)
            REFERENCES aip_action_receipt(org_id,project_id,receipt_id),
          FOREIGN KEY (org_id,project_id,reconcile_attempt_id)
            REFERENCES aip_action_reconcile_attempt(org_id,project_id,reconcile_attempt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_manual_reconcile_decision_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_receipt_id TEXT NOT NULL,
          case_id TEXT NOT NULL, original_receipt_id TEXT NOT NULL,
          resolved_provider_outcome TEXT NOT NULL, resolution_quality TEXT NOT NULL,
          evidence_refs JSONB NOT NULL, maker_id TEXT NOT NULL, checker_id TEXT NOT NULL,
          applied_effect JSONB, compensated_effect JSONB, residual_effect JSONB,
          source_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,decision_receipt_id),
          UNIQUE (org_id,project_id,case_id),
          CHECK (resolved_provider_outcome IN ('applied','failed','partial','unknown')),
          CHECK (resolution_quality IN ('confirmed','insufficient','conflicted')),
          CHECK (maker_id <> checker_id), CHECK (source_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(evidence_refs)='array'),
          FOREIGN KEY (org_id,project_id,case_id)
            REFERENCES aip_action_manual_reconcile_case(org_id,project_id,case_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_compensation_policy_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          policy_id TEXT NOT NULL, revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          lifecycle TEXT NOT NULL, original_action_type_id TEXT NOT NULL,
          allowed_outcomes JSONB NOT NULL, compensation_action_type_id TEXT NOT NULL,
          payload_template JSONB NOT NULL DEFAULT '{}'::jsonb,
          effect_scope_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
          maximum_effect JSONB, risk_floor TEXT NOT NULL,
          approval_policy_ref JSONB, capability_binding_ref JSONB,
          valid_from TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,policy_id,revision),
          UNIQUE (org_id,project_id,policy_id,content_hash),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (lifecycle IN ('draft','published','retired')),
          CHECK (risk_floor IN ('R0','R1','R2','R3','R4')),
          CHECK (jsonb_typeof(allowed_outcomes)='array'
             AND jsonb_typeof(payload_template)='object'
             AND jsonb_typeof(effect_scope_schema)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_compensation_intent (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, intent_id TEXT NOT NULL,
          original_receipt_id TEXT NOT NULL, policy_id TEXT NOT NULL,
          policy_revision BIGINT NOT NULL, policy_hash TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', compensation_proposal_id TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), linked_at TIMESTAMPTZ,
          PRIMARY KEY (org_id,project_id,intent_id),
          UNIQUE (org_id,project_id,original_receipt_id),
          CHECK (policy_hash ~ '^[0-9a-f]{64}$' AND request_hash ~ '^[0-9a-f]{64}$'),
          CHECK (status IN ('pending','linked')),
          FOREIGN KEY (org_id,project_id,original_receipt_id)
            REFERENCES aip_action_receipt(org_id,project_id,receipt_id),
          FOREIGN KEY (org_id,project_id,policy_id,policy_revision)
            REFERENCES aip_action_compensation_policy_revision(org_id,project_id,policy_id,revision)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_compensation_link (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, link_id TEXT NOT NULL,
          original_proposal_id TEXT NOT NULL, original_receipt_id TEXT NOT NULL,
          resolved_outcome_receipt_id TEXT NOT NULL,
          policy_id TEXT NOT NULL, policy_revision BIGINT NOT NULL, policy_hash TEXT NOT NULL,
          compensation_proposal_id TEXT NOT NULL, action_binding_hash TEXT,
          applied_effect JSONB, compensation_effect JSONB, residual_effect JSONB,
          source_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,link_id),
          UNIQUE (org_id,project_id,original_receipt_id),
          UNIQUE (org_id,project_id,compensation_proposal_id),
          CHECK (policy_hash ~ '^[0-9a-f]{64}$' AND source_hash ~ '^[0-9a-f]{64}$'),
          CHECK (action_binding_hash IS NULL OR action_binding_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,original_receipt_id)
            REFERENCES aip_action_receipt(org_id,project_id,receipt_id),
          FOREIGN KEY (org_id,project_id,resolved_outcome_receipt_id)
            REFERENCES aip_action_receipt(org_id,project_id,receipt_id),
          FOREIGN KEY (org_id,project_id,policy_id,policy_revision)
            REFERENCES aip_action_compensation_policy_revision(org_id,project_id,policy_id,revision),
          FOREIGN KEY (org_id,project_id,compensation_proposal_id)
            REFERENCES aip_action_proposal(org_id,project_id,proposal_id)
        )"""
    )
    op.execute(
        """ALTER TABLE aip_action_receipt
        ADD COLUMN provider_outcome TEXT,
        ADD COLUMN reconciliation_status TEXT NOT NULL DEFAULT 'not_required',
        ADD COLUMN resolution_quality TEXT,
        ADD COLUMN resolution_source TEXT,
        ADD COLUMN resolution_cutoff TIMESTAMPTZ,
        ADD COLUMN reconcile_attempt_id TEXT,
        ADD COLUMN manual_reconcile_case_id TEXT,
        ADD COLUMN manual_decision_receipt_id TEXT,
        ADD COLUMN applied_effect JSONB,
        ADD COLUMN compensated_effect JSONB,
        ADD COLUMN residual_effect JSONB,
        ADD CONSTRAINT ck_aip_action_receipt_resolution_w5_004 CHECK (
          (provider_outcome IS NULL OR provider_outcome IN ('accepted','applied','failed','partial','unknown'))
          AND reconciliation_status IN ('not_required','pending','automatic','manual','unresolved')
          AND (resolution_quality IS NULL OR resolution_quality IN ('confirmed','insufficient','conflicted'))
          AND (resolution_source IS NULL OR resolution_source IN ('provider_query','manual_evidence'))
        )"""
    )
    op.execute(
        """ALTER TABLE aip_action_proposal
        ADD COLUMN compensation_original_proposal_id TEXT,
        ADD COLUMN compensation_original_receipt_id TEXT,
        ADD COLUMN compensation_policy_ref JSONB,
        ADD COLUMN compensation_effect JSONB,
        ADD COLUMN compensation_residual_effect JSONB"""
    )
    for table, update in (
        ("aip_action_reconcile_attempt", True),
        ("aip_action_manual_reconcile_case", True),
        ("aip_action_manual_reconcile_decision_receipt", False),
        ("aip_action_compensation_policy_revision", False),
        ("aip_action_compensation_intent", True),
        ("aip_action_compensation_link", False),
    ):
        _scope(table, update=update)
    for table in (
        "aip_action_manual_reconcile_decision_receipt",
        "aip_action_compensation_policy_revision",
        "aip_action_compensation_link",
    ):
        op.execute(
            f"""CREATE TRIGGER {table}_append_only_w5_004
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
        )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS (SELECT 1 FROM aip_action_reconcile_attempt LIMIT 1)
        OR EXISTS (SELECT 1 FROM aip_action_manual_reconcile_case LIMIT 1)
        OR EXISTS (SELECT 1 FROM aip_action_compensation_policy_revision LIMIT 1)
        THEN RAISE EXCEPTION 'cannot downgrade w5_004 with reconciliation facts'
          USING ERRCODE='55000'; END IF; END $$"""
    )
    op.execute("ALTER TABLE aip_action_receipt DROP CONSTRAINT IF EXISTS ck_aip_action_receipt_resolution_w5_004")
    for column in (
        "provider_outcome", "reconciliation_status", "resolution_quality",
        "resolution_source", "resolution_cutoff", "reconcile_attempt_id",
        "manual_reconcile_case_id", "manual_decision_receipt_id",
        "applied_effect", "compensated_effect", "residual_effect",
    ):
        op.execute(f"ALTER TABLE aip_action_receipt DROP COLUMN IF EXISTS {column}")
    for column in (
        "compensation_original_proposal_id", "compensation_original_receipt_id",
        "compensation_policy_ref", "compensation_effect", "compensation_residual_effect",
    ):
        op.execute(f"ALTER TABLE aip_action_proposal DROP COLUMN IF EXISTS {column}")
    for table in (
        "aip_action_compensation_link",
        "aip_action_compensation_intent",
        "aip_action_compensation_policy_revision",
        "aip_action_manual_reconcile_decision_receipt",
        "aip_action_manual_reconcile_case",
        "aip_action_reconcile_attempt",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("ALTER TABLE aip_action_execution_attempt DROP CONSTRAINT IF EXISTS aip_action_execution_attempt_status_check")
    op.execute(
        """ALTER TABLE aip_action_execution_attempt
        ADD CONSTRAINT aip_action_execution_attempt_status_check
        CHECK (status IN ('prepared','dispatch_claimed','accepted','applied','failed','unknown'))"""
    )
