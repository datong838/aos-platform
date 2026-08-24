"""Add dispatch intent, confirmation and Task priority authority (W3-08).

Revision ID: w3_017
Revises: w3_016
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w3_017"
down_revision: str | Sequence[str] | None = "w3_016"
branch_labels = None
depends_on = None

TABLES = (
    "aip_dispatch_intent_revision",
    "aip_dispatch_confirmation_receipt",
    "aip_task_priority_decision_revision",
)


def _protect(name: str) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}_w3_017 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT SELECT,INSERT ON {name} TO aos_runtime")
    op.execute(f"REVOKE UPDATE,DELETE,TRUNCATE ON {name} FROM aos_runtime")
    op.execute(
        f"""CREATE TRIGGER trg_{name}_append_only_w3_017
        BEFORE UPDATE OR DELETE ON {name}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{name}_truncate_guard_w3_017
        BEFORE TRUNCATE ON {name}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_dispatch_intent_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, intent_id TEXT NOT NULL,
          revision BIGINT NOT NULL, task_ref JSONB NOT NULL, task_run_ref JSONB,
          step_run_ref JSONB, responsibility_plan_ref JSONB, command_kind TEXT NOT NULL,
          source_identity TEXT NOT NULL, target_identity TEXT NOT NULL,
          source_slot_id TEXT, target_slot_id TEXT, expected_fence BIGINT,
          reason_code TEXT NOT NULL, policy_ref JSONB NOT NULL, diff JSONB NOT NULL,
          impact JSONB NOT NULL, readiness TEXT NOT NULL, blockers JSONB NOT NULL,
          maker TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          content_hash CHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,intent_id,revision),
          UNIQUE(org_id,project_id,idempotency_key), CHECK(revision>=1),
          CHECK(command_kind IN ('module_handoff','responsibility_successor','runtime_takeover')),
          CHECK(readiness IN ('ready','blocked','confirmed','stale')),
          CHECK(jsonb_typeof(task_ref)='object'), CHECK(jsonb_typeof(policy_ref)='object'),
          CHECK(jsonb_typeof(diff)='object'), CHECK(jsonb_typeof(impact)='object'),
          CHECK(jsonb_typeof(blockers)='array'), CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(content_hash ~ '^[0-9a-f]{64}$')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_dispatch_confirmation_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, confirmation_id TEXT NOT NULL,
          intent_id TEXT NOT NULL, intent_revision BIGINT NOT NULL, intent_content_hash CHAR(64) NOT NULL,
          command_kind TEXT NOT NULL, invocation_state TEXT NOT NULL, checker TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          content_hash CHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,confirmation_id), UNIQUE(org_id,project_id,idempotency_key),
          UNIQUE(org_id,project_id,intent_id,intent_revision),
          CHECK(command_kind IN ('module_handoff','responsibility_successor','runtime_takeover')),
          CHECK(invocation_state='canonical_command_required'),
          CHECK(intent_content_hash ~ '^[0-9a-f]{64}$'), CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,intent_id,intent_revision)
            REFERENCES aip_dispatch_intent_revision(org_id,project_id,intent_id,revision)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_task_priority_decision_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          revision BIGINT NOT NULL, task_ref_before JSONB NOT NULL, task_ref_after JSONB NOT NULL,
          old_priority INTEGER NOT NULL, new_priority INTEGER NOT NULL, reason_code TEXT NOT NULL,
          policy_ref JSONB NOT NULL, actor TEXT NOT NULL, idempotency_key TEXT NOT NULL,
          request_hash CHAR(64) NOT NULL, content_hash CHAR(64) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id,revision), UNIQUE(org_id,project_id,idempotency_key),
          CHECK(revision>=1), CHECK(old_priority BETWEEN 0 AND 100),
          CHECK(new_priority BETWEEN 0 AND 100), CHECK(old_priority<>new_priority),
          CHECK(jsonb_typeof(task_ref_before)='object'), CHECK(jsonb_typeof(task_ref_after)='object'),
          CHECK(jsonb_typeof(policy_ref)='object'), CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(content_hash ~ '^[0-9a-f]{64}$')
        )"""
    )
    for table in TABLES:
        _protect(table)
    op.execute("CREATE INDEX aip_dispatch_intent_task_w3_017 ON aip_dispatch_intent_revision(org_id,project_id,(task_ref->>'resourceId'),created_at DESC)")
    op.execute("CREATE INDEX aip_task_priority_task_w3_017 ON aip_task_priority_decision_revision(org_id,project_id,(task_ref_after->>'resourceId'),created_at DESC)")


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM aip_dispatch_intent_revision LIMIT 1)
          OR EXISTS (SELECT 1 FROM aip_dispatch_confirmation_receipt LIMIT 1)
          OR EXISTS (SELECT 1 FROM aip_task_priority_decision_revision LIMIT 1) THEN
          RAISE EXCEPTION 'cannot downgrade w3_017 with canonical dispatch data' USING ERRCODE='55000';
        END IF;
        END $$"""
    )
    op.execute("DROP TABLE aip_task_priority_decision_revision CASCADE")
    op.execute("DROP TABLE aip_dispatch_confirmation_receipt CASCADE")
    op.execute("DROP TABLE aip_dispatch_intent_revision CASCADE")
