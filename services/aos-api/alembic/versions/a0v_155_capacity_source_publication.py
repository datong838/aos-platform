"""Original fact access for complete Source publication; publication still pending."""
from alembic import op
from aos_api.aip_provider_capacity_publication_transaction import install_original_fact_boundary

revision='a0v_155'
down_revision='a0v_154'
branch_labels=depends_on=None


def upgrade():
    install_original_fact_boundary(op.execute)


def downgrade():
    raise RuntimeError('Original publication facts require explicit reconciliation; no destructive rollback')
