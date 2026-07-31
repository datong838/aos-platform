"""Core-schema baseline migration asset for Wave 0.

The Alembic CLI can render and apply this revision to an isolated empty
database. Runtime DDL outside this core remains registered legacy debt for
later waves. This revision is not a complete production schema snapshot, so
the startup migration control plane neither applies nor stamps it and managed
startup remains fail-closed until the complete snapshot exists.

Revision ID: 6cd2ca0eff8f
Revises: None (baseline)
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '6cd2ca0eff8f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the core schema for a new, empty database."""
    statements = (
        """
        CREATE TABLE meta_object_type (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          published BOOLEAN NOT NULL DEFAULT FALSE,
          properties JSONB NOT NULL DEFAULT '[]'::jsonb,
          required_markings JSONB NOT NULL DEFAULT '[]'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE obj_instance (
          object_type TEXT NOT NULL REFERENCES meta_object_type(id),
          object_id TEXT NOT NULL,
          props JSONB NOT NULL DEFAULT '{}'::jsonb,
          PRIMARY KEY (object_type, object_id)
        )
        """,
        """
        CREATE TABLE graph_edge (
          src_type TEXT NOT NULL,
          src_id TEXT NOT NULL,
          rel TEXT NOT NULL,
          dst_type TEXT NOT NULL,
          dst_id TEXT NOT NULL,
          PRIMARY KEY (src_type, src_id, rel, dst_type, dst_id)
        )
        """,
        """
        CREATE TABLE wiki_page (
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          body JSONB NOT NULL DEFAULT '{}'::jsonb,
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          PRIMARY KEY (object_type, object_id)
        )
        """,
        """
        CREATE TABLE wiki_page_version (
          id BIGSERIAL PRIMARY KEY,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          body JSONB NOT NULL DEFAULT '{}'::jsonb,
          draft_id TEXT,
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX idx_wiki_page_version_obj
          ON wiki_page_version (object_type, object_id, id DESC)
        """,
        """
        CREATE TABLE meta_branch (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          base_ref TEXT NOT NULL DEFAULT 'main',
          readonly BOOLEAN NOT NULL DEFAULT TRUE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE obj_branch_overlay (
          branch_id TEXT NOT NULL REFERENCES meta_branch(id) ON DELETE CASCADE,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          props JSONB NOT NULL DEFAULT '{}'::jsonb,
          op TEXT NOT NULL DEFAULT 'upsert',
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (branch_id, object_type, object_id)
        )
        """,
        """
        CREATE TABLE meta_link_type (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          src_type TEXT NOT NULL,
          dst_type TEXT NOT NULL,
          rel TEXT NOT NULL,
          cardinality TEXT NOT NULL DEFAULT 'MANY_TO_MANY',
          expected_edges BIGINT NOT NULL DEFAULT 0,
          mdo_approved BOOLEAN NOT NULL DEFAULT FALSE,
          published BOOLEAN NOT NULL DEFAULT FALSE,
          description TEXT NOT NULL DEFAULT '',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE funnel_status (
          object_type TEXT PRIMARY KEY,
          stage TEXT NOT NULL DEFAULT 'ingest',
          detail JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """,
        """
        CREATE TABLE authz_tuple (
          user_key TEXT NOT NULL,
          relation TEXT NOT NULL,
          object_key TEXT NOT NULL,
          PRIMARY KEY (user_key, relation, object_key)
        )
        """,
    )
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    """Refuse a destructive downgrade of an adoption baseline.

    Legacy databases may be stamped at this revision, so dropping these tables
    cannot safely distinguish newly-created data from pre-existing data.
    Recovery requires restoring a verified backup into an empty database.
    """
    raise RuntimeError(
        "baseline downgrade is intentionally irreversible; restore a verified "
        "database backup instead"
    )
