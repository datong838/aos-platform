"""Add cost_pending without conflating completed execution and settled money."""
from alembic import op

revision = "a0v_002"
down_revision = "a0v_001"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE aip_budget_reservation DROP CONSTRAINT aip_budget_reservation_state_check")
    op.execute("ALTER TABLE aip_budget_reservation ADD CONSTRAINT aip_budget_reservation_state_check CHECK(state IN ('held','submitted','settled','released','unknown','cost_pending'))")
    op.execute("""CREATE OR REPLACE FUNCTION guard_ar2_budget_reservation_update() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.reservation_id,NEW.invocation_id,
                 NEW.operation_id,NEW.invocation_key,NEW.task_ref,NEW.policy_ref,
                 NEW.pricing_ref,NEW.approval_ref,NEW.currency,NEW.upper_bound_minor,
                 NEW.request_hash,NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.reservation_id,OLD.invocation_id,
                 OLD.operation_id,OLD.invocation_key,OLD.task_ref,OLD.policy_ref,
                 OLD.pricing_ref,OLD.approval_ref,OLD.currency,OLD.upper_bound_minor,
                 OLD.request_hash,OLD.created_at)
          THEN RAISE EXCEPTION 'budget reservation identity is immutable'; END IF;
          IF NEW.revision<>OLD.revision+1 OR NEW.content_hash=OLD.content_hash
             OR NEW.updated_at<OLD.updated_at OR NOT (
               (OLD.state='held' AND NEW.state IN ('submitted','released')) OR
               (OLD.state='submitted' AND NEW.state IN ('settled','released','unknown','cost_pending')) OR
               (OLD.state='unknown' AND NEW.state IN ('settled','released','cost_pending')) OR
               (OLD.state='cost_pending' AND NEW.state='settled'))
          THEN RAISE EXCEPTION 'invalid budget reservation transition'; END IF;
          IF NOT (
            (NEW.state='submitted' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NULL AND jsonb_array_length(NEW.usage_receipt_refs)=0
              AND NEW.actual_minor IS NULL AND NEW.reconciliation_evidence_ref IS NULL) OR
            (NEW.state='unknown' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NULL AND jsonb_array_length(NEW.usage_receipt_refs)=0
              AND NEW.actual_minor IS NULL AND NEW.reconciliation_evidence_ref IS NULL) OR
            (NEW.state='cost_pending' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NOT NULL AND jsonb_array_length(NEW.usage_receipt_refs)>0
              AND NEW.actual_minor IS NULL
              AND jsonb_array_length(NEW.usage_receipt_refs)=(SELECT count(DISTINCT x) FROM jsonb_array_elements(NEW.usage_receipt_refs) x)) OR
            (NEW.state='settled' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NOT NULL AND jsonb_array_length(NEW.usage_receipt_refs)>0
              AND NEW.actual_minor IS NOT NULL) OR
            (NEW.state='released' AND NEW.provider_receipt_ref IS NULL
              AND jsonb_array_length(NEW.usage_receipt_refs)=0 AND NEW.actual_minor IS NULL
              AND ((NEW.provider_request_receipt_ref IS NULL AND NEW.reconciliation_evidence_ref IS NULL)
                OR (NEW.provider_request_receipt_ref IS NOT NULL
                  AND NEW.reconciliation_evidence_ref IS NOT NULL))))
          THEN RAISE EXCEPTION 'budget reservation state shape drifted'; END IF;
          IF OLD.state='cost_pending' AND ROW(NEW.provider_request_receipt_ref,NEW.provider_receipt_ref,NEW.usage_receipt_refs)
             IS DISTINCT FROM ROW(OLD.provider_request_receipt_ref,OLD.provider_receipt_ref,OLD.usage_receipt_refs)
          THEN RAISE EXCEPTION 'completed execution evidence is immutable'; END IF;
          RETURN NEW;
        END $$""")

def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM aip_budget_reservation WHERE state='cost_pending') THEN RAISE EXCEPTION 'pending costs prevent downgrade'; END IF; END $$")
    op.execute("ALTER TABLE aip_budget_reservation DROP CONSTRAINT aip_budget_reservation_state_check")
    op.execute("ALTER TABLE aip_budget_reservation ADD CONSTRAINT aip_budget_reservation_state_check CHECK(state IN ('held','submitted','settled','released','unknown'))")
    op.execute("""CREATE OR REPLACE FUNCTION guard_ar2_budget_reservation_update() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.reservation_id,NEW.invocation_id,
                 NEW.operation_id,NEW.invocation_key,NEW.task_ref,NEW.policy_ref,
                 NEW.pricing_ref,NEW.approval_ref,NEW.currency,NEW.upper_bound_minor,
                 NEW.request_hash,NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.reservation_id,OLD.invocation_id,
                 OLD.operation_id,OLD.invocation_key,OLD.task_ref,OLD.policy_ref,
                 OLD.pricing_ref,OLD.approval_ref,OLD.currency,OLD.upper_bound_minor,
                 OLD.request_hash,OLD.created_at)
          THEN RAISE EXCEPTION 'budget reservation identity is immutable'; END IF;
          IF NEW.revision<>OLD.revision+1 OR NEW.content_hash=OLD.content_hash
             OR NEW.updated_at<OLD.updated_at OR NOT (
               (OLD.state='held' AND NEW.state IN ('submitted','released')) OR
               (OLD.state='submitted' AND NEW.state IN ('settled','released','unknown')) OR
               (OLD.state='unknown' AND NEW.state IN ('settled','released')))
          THEN RAISE EXCEPTION 'invalid budget reservation transition'; END IF;
          IF NOT (
            (NEW.state='submitted' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NULL AND jsonb_array_length(NEW.usage_receipt_refs)=0
              AND NEW.actual_minor IS NULL AND NEW.reconciliation_evidence_ref IS NULL) OR
            (NEW.state='unknown' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NULL AND jsonb_array_length(NEW.usage_receipt_refs)=0
              AND NEW.actual_minor IS NULL AND NEW.reconciliation_evidence_ref IS NULL) OR
            (NEW.state='settled' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NOT NULL AND jsonb_array_length(NEW.usage_receipt_refs)>0
              AND NEW.actual_minor IS NOT NULL) OR
            (NEW.state='released' AND NEW.provider_receipt_ref IS NULL
              AND jsonb_array_length(NEW.usage_receipt_refs)=0 AND NEW.actual_minor IS NULL
              AND ((NEW.provider_request_receipt_ref IS NULL AND NEW.reconciliation_evidence_ref IS NULL)
                OR (NEW.provider_request_receipt_ref IS NOT NULL
                  AND NEW.reconciliation_evidence_ref IS NOT NULL))))
          THEN RAISE EXCEPTION 'budget reservation state shape drifted'; END IF;
          RETURN NEW;
        END $$""")
