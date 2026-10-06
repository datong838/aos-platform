"""Immutable signed authority withdrawal with stable registry epoch invalidation."""
from alembic import op
from aos_api.aip_provider_capacity_withdrawal_registry import install_withdrawal_registry

revision = 'a0v_154'
down_revision = 'a0v_153'
branch_labels = depends_on = None


def upgrade():
    install_withdrawal_registry(op.execute)


def downgrade():
    raise RuntimeError('Preserve signed capacity withdrawal history')
