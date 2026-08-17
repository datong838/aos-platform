"""Add AIP-5 E7 agent memory projection and improvement authorities.

Revision ID: aip5_005
Revises: w2_004
Create Date: 2026-08-14
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip5_005"
down_revision: str | Sequence[str] | None = "w2_004"
branch_labels = None
depends_on = None

TABLES = (
    "aip_memory_agent_projection",
    "aip_memory_agent_projection_recipient",
    "aip_memory_agent_projection_event",
    "aip_memory_agent_projection_receipt",
    "aip_memory_exposure",
    "aip_memory_improvement_observation",
)

APPEND_ONLY_TABLES = TABLES[1:]


def _scope(table: str, *, mutable: bool) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_aip5e7 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    privilege = "SELECT,INSERT,UPDATE" if mutable else "SELECT,INSERT"
    op.execute(f"GRANT {privilege} ON {table} TO aos_runtime")


def _append_only(table: str) -> None:
    op.execute(
        f"""CREATE TRIGGER trg_{table}_append_only
        BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION guard_aip5_e7_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{table}_truncate_guard
        BEFORE TRUNCATE ON {table}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip5_e7_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_memory_agent_projection (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          projection_id TEXT NOT NULL, kind TEXT NOT NULL,
          owner_instance_id TEXT NOT NULL, owner_instance_version BIGINT NOT NULL,
          owner_instance_hash TEXT NOT NULL, owner_instance_ref JSONB NOT NULL,
          memory_item_id TEXT NOT NULL, memory_revision BIGINT NOT NULL,
          memory_hash TEXT NOT NULL, memory_ref JSONB NOT NULL,
          allowed_purposes JSONB NOT NULL, allowed_markings JSONB NOT NULL,
          disclosure TEXT NOT NULL, status TEXT NOT NULL,
          version BIGINT NOT NULL DEFAULT 1, content_hash TEXT NOT NULL,
          effective_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,projection_id),
          CHECK(kind IN ('personal','shared')),
          CHECK(disclosure IN ('citation_only','governed_summary')),
          CHECK(status IN ('active','suspended','revoked','expired','stale')),
          CHECK(owner_instance_version>=1 AND memory_revision>=1 AND version>=1),
          CHECK(owner_instance_hash ~ '^[0-9a-f]{64}$'),
          CHECK(memory_hash ~ '^[0-9a-f]{64}$'),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(expires_at>effective_at),
          CHECK(jsonb_typeof(owner_instance_ref)='object'
            AND owner_instance_ref->>'assetType'='AgentInstance'
            AND owner_instance_ref->>'assetId'=owner_instance_id
            AND (owner_instance_ref->>'revision')::BIGINT=owner_instance_version
            AND owner_instance_ref->>'contentHash'=owner_instance_hash),
          CHECK(jsonb_typeof(memory_ref)='object'
            AND memory_ref->>'memoryItemId'=memory_item_id
            AND (memory_ref->>'revision')::BIGINT=memory_revision
            AND memory_ref->>'contentHash'=memory_hash),
          CHECK(jsonb_typeof(allowed_purposes)='array'
            AND jsonb_array_length(allowed_purposes)>0),
          CHECK(jsonb_typeof(allowed_markings)='array'
            AND jsonb_array_length(allowed_markings)>0),
          FOREIGN KEY(org_id,project_id,owner_instance_id)
            REFERENCES aip_agent_instance(org_id,project_id,instance_id),
          FOREIGN KEY(org_id,project_id,memory_item_id,memory_revision)
            REFERENCES aip_memory_item_revision(org_id,project_id,memory_item_id,revision))"""
    )
    op.execute(
        """CREATE UNIQUE INDEX aip_memory_projection_one_active_exact_idx
        ON aip_memory_agent_projection(
          org_id,project_id,owner_instance_id,owner_instance_version,
          owner_instance_hash,memory_item_id,memory_revision,memory_hash,kind)
        WHERE status='active'"""
    )
    op.execute(
        """CREATE TABLE aip_memory_agent_projection_recipient (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          projection_id TEXT NOT NULL, recipient_instance_id TEXT NOT NULL,
          recipient_instance_version BIGINT NOT NULL,
          recipient_instance_hash TEXT NOT NULL, recipient_instance_ref JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,projection_id,recipient_instance_id,
            recipient_instance_version,recipient_instance_hash),
          CHECK(recipient_instance_version>=1),
          CHECK(recipient_instance_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(recipient_instance_ref)='object'
            AND recipient_instance_ref->>'assetType'='AgentInstance'
            AND recipient_instance_ref->>'assetId'=recipient_instance_id
            AND (recipient_instance_ref->>'revision')::BIGINT=recipient_instance_version
            AND recipient_instance_ref->>'contentHash'=recipient_instance_hash),
          FOREIGN KEY(org_id,project_id,projection_id)
            REFERENCES aip_memory_agent_projection(org_id,project_id,projection_id),
          FOREIGN KEY(org_id,project_id,recipient_instance_id)
            REFERENCES aip_agent_instance(org_id,project_id,instance_id))"""
    )
    op.execute(
        """CREATE TABLE aip_memory_agent_projection_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          event_id TEXT NOT NULL, projection_id TEXT NOT NULL,
          projection_version BIGINT NOT NULL, sequence BIGINT NOT NULL,
          event_type TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL,
          reason_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
          actor TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,event_id),
          UNIQUE(org_id,project_id,projection_id,sequence),
          CHECK(projection_version>=1 AND sequence>=1),
          CHECK(event_type IN ('created','suspended','reactivated','revoked','expired','staled')),
          CHECK(from_status IS NULL OR from_status IN ('active','suspended','revoked','expired','stale')),
          CHECK(to_status IN ('active','suspended','revoked','expired','stale')),
          CHECK(reason_hash ~ '^[0-9a-f]{64}$' AND event_hash ~ '^[0-9a-f]{64}$'),
          CHECK((event_type='created' AND sequence=1 AND from_status IS NULL AND to_status='active')
            OR (event_type<>'created' AND from_status IS NOT NULL)),
          FOREIGN KEY(org_id,project_id,projection_id)
            REFERENCES aip_memory_agent_projection(org_id,project_id,projection_id))"""
    )
    op.execute(
        """CREATE TABLE aip_memory_agent_projection_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, operation TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          projection_id TEXT NOT NULL, projection_version BIGINT NOT NULL,
          projection_hash TEXT NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,receipt_id),
          UNIQUE(org_id,project_id,operation,idempotency_key),
          CHECK(operation IN ('create','suspend','reactivate','revoke')),
          CHECK(projection_version>=1),
          CHECK(request_hash ~ '^[0-9a-f]{64}$' AND projection_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,projection_id)
            REFERENCES aip_memory_agent_projection(org_id,project_id,projection_id))"""
    )
    op.execute(
        """CREATE TABLE aip_memory_exposure (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          exposure_id TEXT NOT NULL, agent_run_id TEXT NOT NULL,
          task_run_id TEXT NOT NULL, instance_id TEXT NOT NULL,
          instance_version BIGINT NOT NULL, instance_hash TEXT NOT NULL,
          skill_ref JSONB NOT NULL, logic_ref JSONB NOT NULL,
          projection_id TEXT NOT NULL, projection_version BIGINT NOT NULL,
          projection_hash TEXT NOT NULL, memory_item_id TEXT NOT NULL,
          memory_revision BIGINT NOT NULL, memory_hash TEXT NOT NULL,
          eval_contract_ref JSONB NOT NULL, time_cutoff TIMESTAMPTZ NOT NULL,
          accepted_at TIMESTAMPTZ NOT NULL, exposure_hash TEXT NOT NULL,
          PRIMARY KEY(org_id,project_id,exposure_id),
          UNIQUE(org_id,project_id,agent_run_id,projection_id,memory_item_id,memory_revision),
          CHECK(instance_version>=1 AND projection_version>=1 AND memory_revision>=1),
          CHECK(instance_hash ~ '^[0-9a-f]{64}$' AND projection_hash ~ '^[0-9a-f]{64}$'
            AND memory_hash ~ '^[0-9a-f]{64}$' AND exposure_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(skill_ref)='object' AND skill_ref->>'assetType'='SkillTemplate'),
          CHECK(jsonb_typeof(logic_ref)='object' AND logic_ref->>'assetType'='LogicRevision'),
          CHECK(jsonb_typeof(eval_contract_ref)='object'
            AND eval_contract_ref->>'assetType'='EvalContract'),
          CHECK(accepted_at>=time_cutoff),
          FOREIGN KEY(org_id,project_id,agent_run_id)
            REFERENCES aip_agent_run(org_id,project_id,agent_run_id),
          FOREIGN KEY(org_id,project_id,task_run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY(org_id,project_id,instance_id)
            REFERENCES aip_agent_instance(org_id,project_id,instance_id),
          FOREIGN KEY(org_id,project_id,projection_id)
            REFERENCES aip_memory_agent_projection(org_id,project_id,projection_id),
          FOREIGN KEY(org_id,project_id,memory_item_id,memory_revision)
            REFERENCES aip_memory_item_revision(org_id,project_id,memory_item_id,revision))"""
    )
    op.execute(
        """CREATE TABLE aip_memory_improvement_observation (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          observation_id TEXT NOT NULL, instance_id TEXT NOT NULL,
          instance_version BIGINT NOT NULL, instance_hash TEXT NOT NULL,
          metric_definition_ref JSONB NOT NULL, eval_contract_ref JSONB NOT NULL,
          eval_report_ref JSONB, baseline_cohort_ref JSONB, treatment_cohort_ref JSONB,
          exposure_refs JSONB NOT NULL, metrics JSONB NOT NULL,
          quality TEXT NOT NULL, source_refs JSONB NOT NULL,
          cutoff_at TIMESTAMPTZ NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
          conclusion TEXT NOT NULL, limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
          observation_hash TEXT NOT NULL,
          PRIMARY KEY(org_id,project_id,observation_id),
          CHECK(instance_version>=1 AND instance_hash ~ '^[0-9a-f]{64}$'),
          CHECK(observation_hash ~ '^[0-9a-f]{64}$'),
          CHECK(quality IN ('measured','estimated','unknown')),
          CHECK(conclusion IN ('improved','unchanged','regressed','insufficient_evidence')),
          CHECK(observed_at>=cutoff_at),
          CHECK(jsonb_typeof(metric_definition_ref)='object'
            AND metric_definition_ref->>'assetType'='MetricDefinition'),
          CHECK(jsonb_typeof(eval_contract_ref)='object'
            AND eval_contract_ref->>'assetType'='EvalContract'),
          CHECK(jsonb_typeof(exposure_refs)='array' AND jsonb_typeof(metrics)='array'
            AND jsonb_typeof(source_refs)='array' AND jsonb_typeof(limitations)='array'),
          CHECK((quality='unknown' AND jsonb_array_length(exposure_refs)=0
              AND jsonb_array_length(metrics)=0 AND jsonb_array_length(source_refs)=0
              AND eval_report_ref IS NULL AND baseline_cohort_ref IS NULL
              AND treatment_cohort_ref IS NULL AND conclusion='insufficient_evidence')
            OR (quality IN ('measured','estimated') AND jsonb_array_length(exposure_refs)>0
              AND jsonb_array_length(metrics)>0 AND jsonb_array_length(source_refs)>0
              AND eval_report_ref IS NOT NULL AND baseline_cohort_ref IS NOT NULL
              AND treatment_cohort_ref IS NOT NULL)),
          FOREIGN KEY(org_id,project_id,instance_id)
            REFERENCES aip_agent_instance(org_id,project_id,instance_id))"""
    )

    op.execute(
        """CREATE FUNCTION guard_aip5_e7_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'AIP5_E7_APPEND_ONLY' USING ERRCODE='55000';
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE FUNCTION guard_aip5_e7_projection_identity() RETURNS trigger AS $$
        BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.projection_id,NEW.kind,
                 NEW.owner_instance_id,NEW.owner_instance_version,NEW.owner_instance_hash,
                 NEW.owner_instance_ref,NEW.memory_item_id,NEW.memory_revision,NEW.memory_hash,
                 NEW.memory_ref,NEW.allowed_purposes,NEW.allowed_markings,NEW.disclosure,
                 NEW.effective_at,NEW.expires_at,NEW.created_by,NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.projection_id,OLD.kind,
                 OLD.owner_instance_id,OLD.owner_instance_version,OLD.owner_instance_hash,
                 OLD.owner_instance_ref,OLD.memory_item_id,OLD.memory_revision,OLD.memory_hash,
                 OLD.memory_ref,OLD.allowed_purposes,OLD.allowed_markings,OLD.disclosure,
                 OLD.effective_at,OLD.expires_at,OLD.created_by,OLD.created_at)
          THEN RAISE EXCEPTION 'AIP5_E7_PROJECTION_IDENTITY_IMMUTABLE' USING ERRCODE='55000'; END IF;
          IF NEW.version<>OLD.version+1 OR NEW.updated_at<=OLD.updated_at
          THEN RAISE EXCEPTION 'AIP5_E7_PROJECTION_CAS_REQUIRED' USING ERRCODE='55000'; END IF;
          IF NOT (
            (OLD.status='active' AND NEW.status IN ('suspended','revoked','expired','stale'))
            OR (OLD.status='suspended' AND NEW.status IN ('active','revoked','expired','stale'))
            OR (OLD.status='stale' AND NEW.status IN ('active','revoked'))
          ) THEN RAISE EXCEPTION 'AIP5_E7_PROJECTION_STATUS_TRANSITION_INVALID' USING ERRCODE='55000'; END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_memory_agent_projection_identity
        BEFORE UPDATE ON aip_memory_agent_projection
        FOR EACH ROW EXECUTE FUNCTION guard_aip5_e7_projection_identity()"""
    )
    for table in APPEND_ONLY_TABLES:
        _append_only(table)
    for table in TABLES:
        _scope(table, mutable=table == "aip_memory_agent_projection")

    op.execute(
        """CREATE INDEX aip_memory_projection_owner_status_idx
        ON aip_memory_agent_projection(
          org_id,project_id,owner_instance_id,status,expires_at,projection_id)"""
    )
    op.execute(
        """CREATE INDEX aip_memory_projection_recipient_lookup_idx
        ON aip_memory_agent_projection_recipient(
          org_id,project_id,recipient_instance_id,projection_id)"""
    )
    op.execute(
        """CREATE INDEX aip_memory_exposure_run_idx
        ON aip_memory_exposure(org_id,project_id,agent_run_id,accepted_at,exposure_id)"""
    )
    op.execute(
        """CREATE INDEX aip_memory_improvement_instance_idx
        ON aip_memory_improvement_observation(
          org_id,project_id,instance_id,observed_at,observation_id)"""
    )


def downgrade() -> None:
    non_empty = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in TABLES)
    op.execute(
        f"""DO $$ BEGIN
          IF {non_empty} THEN
            RAISE EXCEPTION 'AIP5_E7_DOWNGRADE_REQUIRES_EMPTY_TABLES' USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_aip5_e7_projection_identity() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_aip5_e7_append_only() CASCADE")
