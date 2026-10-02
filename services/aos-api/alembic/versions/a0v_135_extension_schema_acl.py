"""Keep shared schema receipts writable only by the maintenance owner."""
from alembic import op


revision = "a0v_135"
down_revision = "a0v_134"
branch_labels = depends_on = None


def upgrade() -> None:
    # TI-2 default table privileges otherwise grant aos_runtime write access.
    op.execute("REVOKE ALL ON public.extension_schema_installation FROM PUBLIC,aos_runtime")
    op.execute("GRANT SELECT ON public.extension_schema_installation TO aos_runtime")


def downgrade() -> None:
    raise RuntimeError("shared schema receipt ACL cannot be silently widened")
