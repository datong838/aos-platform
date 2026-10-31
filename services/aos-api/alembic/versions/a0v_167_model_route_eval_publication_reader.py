"""Candidate least-privilege reader of the original shared publication epoch.

Not deployed or qualified by offline source tests. No original facts/backfill.
"""
from alembic import op
from aos_api.aip_model_route_eval_publication_epoch import install_eval_publication_epoch_reader

revision='a0v_167'
down_revision='a0v_166'
branch_labels=depends_on=None


def upgrade():
    install_eval_publication_epoch_reader(op.execute)


def downgrade():
    raise RuntimeError('publication reader downgrade requires a separately reviewed removal plan')
