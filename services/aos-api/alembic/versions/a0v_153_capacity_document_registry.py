"""Private signed original documents, without Source or execution permissions."""
from alembic import op
from aos_api.aip_provider_capacity_document_registry import install_document_registry

revision = 'a0v_153'
down_revision = 'a0v_152'
branch_labels = depends_on = None


def upgrade():
    install_document_registry(op.execute)


def downgrade():
    raise RuntimeError('Preserve original capacity documents and signature provenance')
