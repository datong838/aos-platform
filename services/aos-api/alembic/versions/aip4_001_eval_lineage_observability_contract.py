"""AIP-4 Eval, release, lineage, and usage authority contracts.

Revision ID: aip4_001
Revises: aip3b_002
Create Date: 2026-08-11
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip4_001"
down_revision: str | Sequence[str] | None = "aip3b_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SCOPED_TABLES = (
    "aip_eval_dataset_revision",
    "aip_eval_run",
    "aip_eval_run_event",
    "aip_release_gate_decision",
    "aip_publication_event",
    "aip_lineage_event",
    "aip_usage_receipt",
    "aip_usage_adjustment",
    "aip_metric_definition_revision",
)

_APPEND_ONLY_TABLES = (
    "aip_eval_dataset_revision",
    "aip_eval_run_event",
    "aip_release_gate_decision",
    "aip_publication_event",
    "aip_lineage_event",
    "aip_usage_receipt",
    "aip_usage_adjustment",
    "aip_metric_definition_revision",
)


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_eval_dataset_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          dataset_id TEXT NOT NULL, revision BIGINT NOT NULL,
          content_hash TEXT NOT NULL, source_hash TEXT NOT NULL,
          redaction_policy_ref JSONB NOT NULL, manifest JSONB NOT NULL,
          actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,dataset_id,revision),
          UNIQUE (org_id,project_id,dataset_id,content_hash),
          CHECK (revision >= 1), CHECK (length(content_hash)=64),
          CHECK (length(source_hash)=64),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_eval_run (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
          suite_id TEXT NOT NULL, suite_revision BIGINT NOT NULL,
          suite_hash TEXT NOT NULL, target_ref JSONB NOT NULL,
          dataset_ref JSONB NOT NULL, judge_ref JSONB NOT NULL,
          status TEXT NOT NULL, idempotency_key TEXT NOT NULL,
          version BIGINT NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), started_at TIMESTAMPTZ,
          finished_at TIMESTAMPTZ,
          PRIMARY KEY (org_id,project_id,run_id),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (suite_revision >= 1), CHECK (length(suite_hash)=64),
          CHECK (version >= 1),
          CHECK (status IN ('queued','running','succeeded','failed','cancelled','unknown')),
          CHECK (finished_at IS NULL OR started_at IS NOT NULL),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_eval_run_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          run_id TEXT NOT NULL, sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
          from_status TEXT, to_status TEXT NOT NULL, payload_hash TEXT NOT NULL,
          actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,event_id),
          UNIQUE (org_id,project_id,run_id,sequence),
          CHECK (sequence >= 1), CHECK (length(payload_hash)=64),
          CHECK (from_status IS NULL OR from_status IN ('queued','running','succeeded','failed','cancelled','unknown')),
          CHECK (to_status IN ('queued','running','succeeded','failed','cancelled','unknown')),
          FOREIGN KEY (org_id,project_id,run_id)
            REFERENCES aip_eval_run(org_id,project_id,run_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_release_gate_decision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          target_ref JSONB NOT NULL, suite_ref JSONB NOT NULL,
          eval_run_id TEXT NOT NULL, eval_report_ref JSONB NOT NULL,
          status TEXT NOT NULL, decision_hash TEXT NOT NULL,
          invalidated_by TEXT, decided_by TEXT NOT NULL,
          decided_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,decision_id),
          CHECK (status IN ('passed','failed','blocked','invalidated')),
          CHECK (length(decision_hash)=64),
          CHECK ((status='invalidated' AND invalidated_by IS NOT NULL)
              OR (status<>'invalidated' AND invalidated_by IS NULL)),
          FOREIGN KEY (org_id,project_id,eval_run_id)
            REFERENCES aip_eval_run(org_id,project_id,run_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_publication_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          publication_id TEXT NOT NULL, target_ref JSONB NOT NULL,
          event_type TEXT NOT NULL, release_gate_decision_id TEXT NOT NULL,
          reason_hash TEXT NOT NULL, actor TEXT NOT NULL,
          occurred_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,event_id),
          CHECK (event_type IN ('published','revoked','suspended','deprecated')),
          CHECK (length(reason_hash)=64),
          FOREIGN KEY (org_id,project_id,release_gate_decision_id)
            REFERENCES aip_release_gate_decision(org_id,project_id,decision_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_lineage_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          lineage_id TEXT NOT NULL, root_type TEXT NOT NULL, root_id TEXT NOT NULL,
          sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
          subject_ref JSONB, artifact_ref JSONB, payload_hash TEXT NOT NULL,
          quality TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
          observed_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,event_id),
          UNIQUE (org_id,project_id,lineage_id,sequence),
          CHECK (root_type IN ('task_run','action','research_job','legacy_decision_lineage')),
          CHECK (event_type IN ('input','retrieval','model','tool','action','artifact','eval','approval','receipt','effect_review','memory_candidate','fallback','reconcile','error')),
          CHECK (quality IN ('measured','estimated','unknown')),
          CHECK (sequence >= 1), CHECK (length(payload_hash)=64),
          CHECK (observed_at >= occurred_at),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_usage_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          provider TEXT NOT NULL, provider_receipt_id TEXT NOT NULL,
          lineage_id TEXT NOT NULL, usage_kind TEXT NOT NULL,
          quantity DOUBLE PRECISION NOT NULL, unit TEXT NOT NULL,
          currency TEXT, quality TEXT NOT NULL, source_hash TEXT NOT NULL,
          observed_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,receipt_id),
          UNIQUE (org_id,project_id,provider,provider_receipt_id),
          CHECK (usage_kind IN ('input_token','output_token','cached_token','cost','latency','tool_unit')),
          CHECK (quality IN ('measured','estimated','unknown')),
          CHECK (quantity >= 0), CHECK (length(source_hash)=64),
          CHECK ((usage_kind='cost' AND currency ~ '^[A-Z]{3}$')
              OR (usage_kind<>'cost' AND currency IS NULL)),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_usage_adjustment (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, adjustment_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, delta DOUBLE PRECISION NOT NULL,
          reason_hash TEXT NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,adjustment_id),
          CHECK (length(reason_hash)=64),
          FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES aip_usage_receipt(org_id,project_id,receipt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_metric_definition_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          metric_id TEXT NOT NULL, revision BIGINT NOT NULL,
          content_hash TEXT NOT NULL, definition JSONB NOT NULL,
          actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,metric_id,revision),
          UNIQUE (org_id,project_id,metric_id,content_hash),
          CHECK (revision >= 1), CHECK (length(content_hash)=64),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )

    for table in _SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_aip4 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )

    op.execute(
        """CREATE FUNCTION guard_aip4_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'AIP4_APPEND_ONLY' USING ERRCODE='55000';
        END;
        $$ LANGUAGE plpgsql"""
    )
    for table in _APPEND_ONLY_TABLES:
        op.execute(
            f"""CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
        )
        op.execute(
            f"""CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
        )

    for table in _APPEND_ONLY_TABLES:
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")
    op.execute("GRANT SELECT,INSERT,UPDATE ON aip_eval_run TO aos_runtime")


def downgrade() -> None:
    for table in reversed(_SCOPED_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_aip4_append_only()")
