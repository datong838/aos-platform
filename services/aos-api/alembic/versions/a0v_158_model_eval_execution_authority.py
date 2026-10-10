"""Closed Model proof storage. No Model runtime admission or trusted writer."""
from alembic import op
from aos_api.aip_model_eval_execution_authority import (
    install_closed_storage, install_closed_issuer_history, install_closed_certificate_epochs,
)

revision = 'a0v_158'
down_revision = 'a0v_157'
branch_labels = depends_on = None


def upgrade():
    install_closed_storage(op.execute)
    install_closed_issuer_history(op.execute)
    install_closed_certificate_epochs(op.execute)


def downgrade():
    raise RuntimeError('Immutable Model proof history requires explicit reconciliation; no destructive rollback')
