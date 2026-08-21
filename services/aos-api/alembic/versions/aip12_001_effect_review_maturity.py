"""Add EffectReviewRevision and EffectMaturityDecision authority (W-L19).

Revision ID: aip12_001
Revises: aip11_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip12_001"
down_revision: str | Sequence[str] | None = "aip11_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(name: str, grant: str = "SELECT,INSERT") -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}
           ON {name} TO aos_runtime
           USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))
           WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT {grant} ON {name} TO aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_effect_review_head (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          current_revision BIGINT NOT NULL,
          version BIGINT NOT NULL DEFAULT 1,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, subject_id),
          CHECK (current_revision >= 1),
          CHECK (version >= 1)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_effect_review_revision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          review_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          revision BIGINT NOT NULL,
          subject_ref JSONB NOT NULL,
          observation_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          metric_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
          sample_count INTEGER NOT NULL DEFAULT 0,
          min_sample INTEGER NOT NULL DEFAULT 1,
          cutoff_at TIMESTAMPTZ NOT NULL,
          event_time_at TIMESTAMPTZ NOT NULL,
          accepted BOOLEAN NOT NULL DEFAULT FALSE,
          effect_completed BOOLEAN NOT NULL DEFAULT FALSE,
          maturity_status TEXT NOT NULL,
          reason_code TEXT NOT NULL,
          content_hash CHAR(64) NOT NULL,
          actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, review_id),
          UNIQUE (org_id, project_id, subject_id, revision),
          CHECK (revision >= 1),
          CHECK (sample_count >= 0),
          CHECK (min_sample >= 1),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (maturity_status IN ('immature','mature','insufficient','unknown')),
          CHECK (jsonb_typeof(subject_ref)='object'),
          CHECK (jsonb_typeof(observation_refs)='array'),
          CHECK (jsonb_typeof(metric_keys)='array')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_effect_maturity_decision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          decision_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          review_id TEXT NOT NULL,
          review_revision BIGINT NOT NULL,
          maturity_status TEXT NOT NULL,
          accepted BOOLEAN NOT NULL,
          effect_completed BOOLEAN NOT NULL,
          sample_count INTEGER NOT NULL,
          min_sample INTEGER NOT NULL,
          cutoff_at TIMESTAMPTZ NOT NULL,
          observed_at TIMESTAMPTZ NOT NULL,
          reason_code TEXT NOT NULL,
          actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, decision_id),
          CHECK (review_revision >= 1),
          CHECK (maturity_status IN ('immature','mature','insufficient','unknown')),
          FOREIGN KEY (org_id, project_id, review_id)
            REFERENCES aip_effect_review_revision(org_id, project_id, review_id)
            ON DELETE RESTRICT
        )"""
    )
    _rls("aip_effect_review_head", "SELECT,INSERT,UPDATE")
    _rls("aip_effect_review_revision", "SELECT,INSERT")
    _rls("aip_effect_maturity_decision", "SELECT,INSERT")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_effect_maturity_decision CASCADE")
    op.execute("DROP TABLE IF EXISTS aip_effect_review_revision CASCADE")
    op.execute("DROP TABLE IF EXISTS aip_effect_review_head CASCADE")
