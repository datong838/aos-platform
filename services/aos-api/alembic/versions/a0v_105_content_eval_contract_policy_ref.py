"""Allow an exact EvalContract revision to carry its embedded content gate policy.

Revision ID: a0v_105
Revises: a0v_104
"""

from alembic import op


revision = "a0v_105"
down_revision = "a0v_104"
branch_labels = depends_on = None


def upgrade() -> None:
    for table, constraint in (
        ("aip_eval_run", "ck_eval_run_gate_policy_w7_004"),
        ("aip_eval_report_revision", "ck_eval_report_gate_policy_w7_004"),
    ):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {constraint}")
        op.execute(f"""ALTER TABLE public.{table} ADD CONSTRAINT {constraint} CHECK (
          gate_policy_ref IS NULL OR (
            jsonb_typeof(gate_policy_ref)='object'
            AND gate_policy_ref->>'resourceType' IN
              ('MediaGatePolicyRevision','EvalContractRevision')
            AND (gate_policy_ref->>'resourceType'='MediaGatePolicyRevision'
              OR char_length(COALESCE(gate_policy_ref->>'resourceId','')) BETWEEN 1 AND 200)
            AND (gate_policy_ref->>'revision') ~ '^[1-9][0-9]*$'
            AND (gate_policy_ref->>'contentHash') ~ '^[0-9a-f]{{64}}$'))""")


def downgrade() -> None:
    for table, constraint in (
        ("aip_eval_run", "ck_eval_run_gate_policy_w7_004"),
        ("aip_eval_report_revision", "ck_eval_report_gate_policy_w7_004"),
    ):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {constraint}")
        op.execute(f"""ALTER TABLE public.{table} ADD CONSTRAINT {constraint} CHECK (
          gate_policy_ref IS NULL OR (
            jsonb_typeof(gate_policy_ref)='object'
            AND gate_policy_ref->>'resourceType'='MediaGatePolicyRevision'
            AND (gate_policy_ref->>'revision') ~ '^[1-9][0-9]*$'
            AND (gate_policy_ref->>'contentHash') ~ '^[0-9a-f]{{64}}$'))""")
