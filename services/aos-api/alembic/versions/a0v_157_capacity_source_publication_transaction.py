"""Audited private Source transaction foundation; public issuance still gated."""
from alembic import op
from psycopg.rows import dict_row

from aos_api.aip_provider_capacity_publication_transaction import (
    install_source_transaction_boundary,
    require_source_transaction_tables,
)

revision = 'a0v_157'
down_revision = 'a0v_156'
branch_labels = depends_on = None


def upgrade():
    # Alembic owns the native transaction: any install/audit error rolls back
    # the whole migration. No public entry, issuer grant, signer or activation.
    connection = op.get_bind().connection.driver_connection
    with connection.cursor(row_factory=dict_row) as catalog:
        # Execute the trusted body verbatim: SQLAlchemy text() would treat
        # JSON ':25' literals as binds. Never rewrite signed/frozen SQL bodies.
        install_source_transaction_boundary(catalog.execute)
        require_source_transaction_tables(catalog)


def downgrade():
    raise RuntimeError('Source records require explicit reconciliation; no destructive rollback')
