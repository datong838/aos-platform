"""Declare capability invocation lineage without impersonating a TaskRun."""
from alembic import op
revision='a0v_004'
down_revision='a0v_003'
branch_labels=None
depends_on=None
ROOTS="'task_run','action','eval_run','publication','research_job','legacy_decision_lineage'"
SOURCES="'task_run','step_run','checkpoint','artifact','evidence','action_event','action_receipt','eval_run','eval_run_event','eval_report','publication_event'"


def _constraints(roots,sources):
    for column,values in [('root_type',roots),('source_kind',sources)]:
        op.execute(f'ALTER TABLE aip_lineage_event DROP CONSTRAINT aip_lineage_event_{column}_check')
        op.execute(f'ALTER TABLE aip_lineage_event ADD CONSTRAINT aip_lineage_event_{column}_check CHECK({column} IN ({values}))')


def upgrade():
    _constraints(ROOTS+",'capability_invocation'",SOURCES+",'capability_provider_result'")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM aip_lineage_event WHERE root_type='capability_invocation' OR source_kind='capability_provider_result') THEN RAISE EXCEPTION 'capability lineage evidence prevents downgrade'; END IF; END $$""")
    _constraints(ROOTS,SOURCES)
