"""Make canonical JSON hashing independent of the caller's search path."""
from alembic import op

revision = "a0v_011"
down_revision = "a0v_010"
branch_labels = None
depends_on = None


def upgrade():
    # pg_restore clears search_path. Recursive calls must still resolve the
    # authoritative function, rather than fail or use a caller-owned overload.
    op.execute("""
        ALTER FUNCTION public.canonical_asset_registry_jsonb(jsonb)
        SET search_path = pg_catalog, public, pg_temp
    """)


def downgrade():
    raise RuntimeError("Forward-only canonical hash fix: caller-controlled lookup is unsafe")
