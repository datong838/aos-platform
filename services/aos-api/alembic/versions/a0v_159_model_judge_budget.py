"""Separate Judge-call budget identity; shared original fee buckets."""
from alembic import op
from aos_api.aip_model_eval_judge_budget_authority import judge_budget_statements

revision = 'a0v_159'
down_revision = 'a0v_158'
branch_labels = depends_on = None


def upgrade():
    for statement in judge_budget_statements():
        op.execute(statement)


def downgrade():
    raise RuntimeError('Judge budget evidence requires explicit reconciliation; no destructive rollback')
