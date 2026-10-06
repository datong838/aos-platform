"""Private empty root registry; no configured anchor or root registration."""
from alembic import op
from aos_api.aip_provider_capacity_publication_registry import install_registry_schema

revision = 'a0v_152'
down_revision = 'a0v_151'
branch_labels = depends_on = None


def upgrade():
    install_registry_schema(op.execute)


def downgrade():
    raise RuntimeError('Capacity root registry is irreversible; preserve original anchor/documents/epochs')
