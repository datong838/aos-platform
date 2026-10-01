"""Original maker boundary and genuinely read-only budget receipt recovery."""
from pathlib import Path
from alembic import op

revision = 'a0v_127'
down_revision = 'a0v_126'
branch_labels = depends_on = None


def upgrade():
    source = Path(__file__).resolve().parents[2] / 'aos_api/aip_budget_consumer_actor.sql'
    op.get_bind().exec_driver_sql(source.read_text().replace('%', '%%'))
    for name, count in [('aip_budget_cost_actor_a0v_127', 5),
                        ('aip_consume_budget_as_actor_a0v_127', 6),
                        ('aip_reconcile_budget_as_actor_a0v_127', 6)]:
        signature = 'public.' + name + '(' + ','.join(['text']*count) + ')'
        op.execute(f'ALTER FUNCTION {signature} OWNER TO aos_budget_consumer_owner')
        op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
        if count == 6:
            op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_budget_consumer_call')
    op.execute('REVOKE EXECUTE ON FUNCTION public.aip_consume_budget_cost_a0v_126(text,text,text,text) FROM aos_budget_consumer_call')


def downgrade():
    raise RuntimeError('budget actor and receipt history boundary must not be removed')
