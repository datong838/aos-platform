"""Exact original epoch locks for the controlled publication Owner."""
from alembic import op
from aos_api.aip_provider_capacity_publication_lock_boundary import install_publication_epoch_locks

revision='a0v_156'
down_revision='a0v_155'
branch_labels=depends_on=None


def upgrade():
    install_publication_epoch_locks(op.execute)


def downgrade():
    raise RuntimeError('Publication epoch access requires explicit reconciliation; no silent rollback')
