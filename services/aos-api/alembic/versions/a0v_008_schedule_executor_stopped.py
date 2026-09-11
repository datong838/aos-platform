"""Record proven local executor termination; old runs remain unknown."""
from alembic import op

revision = 'a0v_008'
down_revision = 'a0v_007'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE meta_schedule_run ADD COLUMN executor_stopped BOOLEAN NOT NULL DEFAULT false')


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM meta_schedule_run WHERE executor_stopped) THEN
            RAISE EXCEPTION 'executor termination evidence prevents downgrade' USING ERRCODE='55000';
        END IF;
    END $$""")
    op.execute('ALTER TABLE meta_schedule_run DROP COLUMN executor_stopped')
