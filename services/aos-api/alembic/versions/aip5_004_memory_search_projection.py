"""Add tenant-scoped rebuildable knowledge search projections.

Revision ID: aip5_004
Revises: aip5_003
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "aip5_004"
down_revision: str | Sequence[str] | None = "aip5_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _scope(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_aip5 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_memory_search_reference (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          memory_item_id TEXT NOT NULL, revision BIGINT NOT NULL,
          content_hash TEXT NOT NULL, subject_ref JSONB NOT NULL,
          source_id TEXT NOT NULL, source_revision BIGINT NOT NULL,
          source_ref JSONB NOT NULL, search_terms JSONB NOT NULL,
          search_text TEXT NOT NULL, markings JSONB NOT NULL,
          applicability JSONB NOT NULL, freshness_expires_at TIMESTAMPTZ NOT NULL,
          indexed_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,memory_item_id,revision),
          CHECK (revision >= 1), CHECK (source_revision >= 1),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(subject_ref)='object'),
          CHECK (jsonb_typeof(source_ref)='object'),
          CHECK (jsonb_typeof(search_terms)='array'
             AND jsonb_array_length(search_terms) BETWEEN 1 AND 64),
          CHECK (length(search_text) BETWEEN 1 AND 4096),
          CHECK (jsonb_typeof(markings)='array'
             AND jsonb_array_length(markings)>0),
          CHECK (jsonb_typeof(applicability)='array'
             AND jsonb_array_length(applicability)>0),
          FOREIGN KEY (org_id,project_id,memory_item_id,revision)
            REFERENCES aip_memory_item_revision(org_id,project_id,memory_item_id,revision)
            ON DELETE CASCADE,
          FOREIGN KEY (org_id,project_id,source_id,source_revision)
            REFERENCES aip_memory_source_revision(org_id,project_id,source_id,revision)
        )"""
    )
    op.execute(
        """CREATE INDEX aip_memory_search_reference_fulltext_idx
        ON aip_memory_search_reference
        USING GIN (to_tsvector('simple', search_text))"""
    )
    op.execute(
        """CREATE INDEX aip_memory_search_reference_freshness_idx
        ON aip_memory_search_reference
          (org_id,project_id,freshness_expires_at,memory_item_id,revision)"""
    )
    _scope("aip_memory_search_reference")
    op.execute(
        """GRANT SELECT,INSERT,UPDATE,DELETE
        ON aip_memory_search_reference TO aos_runtime"""
    )

    op.execute(
        """CREATE TABLE aip_memory_search_capability (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          lane TEXT NOT NULL, status TEXT NOT NULL,
          provider TEXT, provider_revision TEXT, reason_code TEXT,
          version BIGINT NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,lane),
          CHECK (lane IN ('fulltext','vector','rerank')),
          CHECK (status IN ('unbuilt','ready','degraded','blocked')),
          CHECK (version >= 1),
          CHECK ((status='ready' AND provider IS NOT NULL
                  AND provider_revision IS NOT NULL AND reason_code IS NULL)
             OR (status<>'ready' AND reason_code IS NOT NULL)),
          FOREIGN KEY (org_id,project_id)
            REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    _scope("aip_memory_search_capability")
    op.execute(
        """GRANT SELECT,INSERT,UPDATE
        ON aip_memory_search_capability TO aos_runtime"""
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_memory_search_capability")
    op.execute("DROP TABLE IF EXISTS aip_memory_search_reference")
