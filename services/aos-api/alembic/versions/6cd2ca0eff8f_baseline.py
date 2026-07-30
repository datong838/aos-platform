"""Baseline migration — marks current schema as v1.

This is a no-op: all tables already exist via init_schema() in db.py.
Future migrations will use op.execute() with raw SQL to add/modify tables.

Revision ID: 6cd2ca0eff8f
Revises: None (baseline)
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6cd2ca0eff8f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
