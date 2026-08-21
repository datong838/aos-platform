"""Add durable AgentRun execution-attempt authority.

Revision ID: aip10_006
Revises: aip10_005
Create Date: 2026-08-17
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "aip10_006"
down_revision: str | Sequence[str] | None = "aip10_005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_agent_run_execution_attempt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          attempt_id TEXT NOT NULL, agent_run_id TEXT NOT NULL,
          agent_run_version BIGINT NOT NULL, attempt_no BIGINT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          route_ref JSONB NOT NULL, policy_ref JSONB NOT NULL,
          model_ref JSONB NOT NULL, provider_ref JSONB NOT NULL,
          price_snapshot_ref JSONB NOT NULL, budget_ref JSONB NOT NULL,
          capacity_reservation_ref JSONB NOT NULL,
          data_classification TEXT NOT NULL, lineage_id TEXT NOT NULL,
          status TEXT NOT NULL, provider_receipt_id TEXT,
          usage_receipt_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
          output_artifact_ref JSONB, reason_code TEXT,
          version BIGINT NOT NULL DEFAULT 1,
          prepared_at TIMESTAMPTZ NOT NULL,
          invoking_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
          created_by TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,attempt_id),
          UNIQUE(org_id,project_id,agent_run_id,attempt_no),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(agent_run_version>=1 AND attempt_no>=1 AND version>=1),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(status IN ('prepared','invoking','succeeded','failed','unknown')),
          CHECK(data_classification IN ('public','internal','confidential')),
          CHECK(jsonb_typeof(route_ref)='object' AND jsonb_typeof(policy_ref)='object'),
          CHECK(jsonb_typeof(model_ref)='object' AND jsonb_typeof(provider_ref)='object'),
          CHECK(jsonb_typeof(price_snapshot_ref)='object' AND jsonb_typeof(budget_ref)='object'),
          CHECK(jsonb_typeof(capacity_reservation_ref)='object'),
          CHECK(jsonb_typeof(usage_receipt_ids)='array'),
          CHECK(output_artifact_ref IS NULL OR jsonb_typeof(output_artifact_ref)='object'),
          CHECK((status='prepared' AND invoking_at IS NULL AND completed_at IS NULL
                 AND provider_receipt_id IS NULL AND jsonb_array_length(usage_receipt_ids)=0
                 AND output_artifact_ref IS NULL AND reason_code IS NULL)
             OR (status='invoking' AND invoking_at IS NOT NULL AND completed_at IS NULL
                 AND provider_receipt_id IS NULL AND jsonb_array_length(usage_receipt_ids)=0
                 AND output_artifact_ref IS NULL AND reason_code IS NULL)
             OR (status='succeeded' AND invoking_at IS NOT NULL AND completed_at IS NOT NULL
                 AND NULLIF(provider_receipt_id,'') IS NOT NULL
                 AND jsonb_array_length(usage_receipt_ids)>0
                 AND output_artifact_ref IS NOT NULL AND reason_code IS NULL)
             OR (status IN ('failed','unknown') AND completed_at IS NOT NULL
                 AND NULLIF(reason_code,'') IS NOT NULL)),
          FOREIGN KEY(org_id,project_id,agent_run_id)
            REFERENCES aip_agent_run(org_id,project_id,agent_run_id))"""
    )
    op.execute(
        """CREATE FUNCTION guard_aip10_agent_run_attempt_identity() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.attempt_id,NEW.agent_run_id,
                 NEW.agent_run_version,NEW.attempt_no,NEW.idempotency_key,NEW.request_hash,
                 NEW.route_ref,NEW.policy_ref,NEW.model_ref,NEW.provider_ref,
                 NEW.price_snapshot_ref,NEW.budget_ref,NEW.capacity_reservation_ref,
                 NEW.data_classification,NEW.lineage_id,NEW.prepared_at,NEW.created_by)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.attempt_id,OLD.agent_run_id,
                 OLD.agent_run_version,OLD.attempt_no,OLD.idempotency_key,OLD.request_hash,
                 OLD.route_ref,OLD.policy_ref,OLD.model_ref,OLD.provider_ref,
                 OLD.price_snapshot_ref,OLD.budget_ref,OLD.capacity_reservation_ref,
                 OLD.data_classification,OLD.lineage_id,OLD.prepared_at,OLD.created_by)
          THEN RAISE EXCEPTION 'agent run execution attempt identity is immutable'; END IF;
          RETURN NEW;
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_agent_run_execution_attempt_identity
        BEFORE UPDATE ON aip_agent_run_execution_attempt
        FOR EACH ROW EXECUTE FUNCTION guard_aip10_agent_run_attempt_identity()"""
    )
    op.execute("ALTER TABLE aip_agent_run_execution_attempt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_agent_run_execution_attempt FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_aip_agent_run_execution_attempt ON
        aip_agent_run_execution_attempt TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        "GRANT SELECT,INSERT,UPDATE ON aip_agent_run_execution_attempt TO aos_runtime"
    )
    op.execute(
        """CREATE INDEX aip_agent_run_execution_attempt_list_idx
        ON aip_agent_run_execution_attempt(org_id,project_id,agent_run_id,attempt_no DESC)"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_agent_run_execution_attempt) THEN
            RAISE EXCEPTION 'AIP10_006_DOWNGRADE_REQUIRES_EMPTY_ATTEMPT_AUTHORITY'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    op.execute("DROP TABLE aip_agent_run_execution_attempt")
    op.execute("DROP FUNCTION guard_aip10_agent_run_attempt_identity()")
