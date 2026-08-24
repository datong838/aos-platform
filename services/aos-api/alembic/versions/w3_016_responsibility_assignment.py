"""Add responsibility successor and takeover assignment authority (W3-07).

Revision ID: w3_016
Revises: w3_015
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w3_016"
down_revision: str | Sequence[str] | None = "w3_015"
branch_labels = None
depends_on = None


APPEND_ONLY = (
    "aip_responsibility_successor",
    "aip_takeover_request",
    "aip_takeover_decision_revision",
)


def _tenant_table(name: str, grants: str) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}_w3_016 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT {grants} ON {name} TO aos_runtime")


def _append_only(name: str) -> None:
    op.execute(f"REVOKE UPDATE,DELETE,TRUNCATE ON {name} FROM aos_runtime")
    op.execute(
        f"""CREATE TRIGGER trg_{name}_append_only_w3_016
        BEFORE UPDATE OR DELETE ON {name}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{name}_truncate_guard_w3_016
        BEFORE TRUNCATE ON {name}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_responsibility_successor (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, successor_id TEXT NOT NULL,
          task_id TEXT NOT NULL, source_plan_ref JSONB NOT NULL, successor_plan_ref JSONB NOT NULL,
          slot_id TEXT NOT NULL, source_assignee JSONB NOT NULL, target_assignee JSONB NOT NULL,
          resolution_receipt_id TEXT NOT NULL, reason_code TEXT NOT NULL, actor TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          content_hash CHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,successor_id),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(jsonb_typeof(source_plan_ref)='object'),
          CHECK(jsonb_typeof(successor_plan_ref)='object'),
          CHECK(jsonb_typeof(source_assignee)='object'),
          CHECK(jsonb_typeof(target_assignee)='object'),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,task_id) REFERENCES aip_task(org_id,project_id,task_id),
          FOREIGN KEY(org_id,project_id,resolution_receipt_id)
            REFERENCES aip_assignee_resolution_receipt(org_id,project_id,receipt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_takeover_request (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, request_id TEXT NOT NULL,
          task_run_ref JSONB NOT NULL, step_run_ref JSONB NOT NULL, attempt INTEGER NOT NULL,
          source_owner JSONB NOT NULL, target_owner JSONB NOT NULL,
          resolution_receipt_id TEXT NOT NULL, expected_fence BIGINT NOT NULL,
          reason_code TEXT NOT NULL, safety_state TEXT NOT NULL, status TEXT NOT NULL,
          blockers JSONB NOT NULL DEFAULT '[]'::jsonb, maker TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          content_hash CHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,request_id), UNIQUE(org_id,project_id,idempotency_key),
          CHECK(attempt>=1), CHECK(expected_fence>=0),
          CHECK(safety_state IN ('safe_checkpoint','active_lease','provider_outcome_unknown','step_terminal')),
          CHECK(status IN ('pending','blocked')), CHECK(jsonb_typeof(blockers)='array'),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,resolution_receipt_id)
            REFERENCES aip_assignee_resolution_receipt(org_id,project_id,receipt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_execution_assignment_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
          step_run_id TEXT NOT NULL, attempt INTEGER NOT NULL, owner JSONB NOT NULL,
          current_fence BIGINT NOT NULL, lease_id TEXT NOT NULL, lease_expires_at TIMESTAMPTZ NOT NULL,
          version BIGINT NOT NULL DEFAULT 1, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,step_run_id,attempt),
          UNIQUE(org_id,project_id,lease_id), CHECK(attempt>=1),
          CHECK(current_fence>=1), CHECK(version>=1), CHECK(jsonb_typeof(owner)='object'),
          FOREIGN KEY(org_id,project_id,run_id) REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY(org_id,project_id,step_run_id) REFERENCES aip_step_run(org_id,project_id,step_run_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_takeover_decision_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          request_id TEXT NOT NULL, revision BIGINT NOT NULL, decision TEXT NOT NULL,
          reason_code TEXT NOT NULL, checker TEXT NOT NULL, assignment_lease JSONB,
          idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          content_hash CHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id,revision),
          UNIQUE(org_id,project_id,request_id), UNIQUE(org_id,project_id,idempotency_key),
          CHECK(revision>=1), CHECK(decision IN ('approved','rejected')),
          CHECK((decision='approved')=(assignment_lease IS NOT NULL)),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,request_id)
            REFERENCES aip_takeover_request(org_id,project_id,request_id)
        )"""
    )
    for table in (*APPEND_ONLY, "aip_execution_assignment_head"):
        _tenant_table(table, "SELECT,INSERT" if table in APPEND_ONLY else "SELECT,INSERT,UPDATE")
    for table in APPEND_ONLY:
        _append_only(table)
    op.execute(
        "CREATE INDEX aip_takeover_request_step_w3_016 ON "
        "aip_takeover_request(org_id,project_id,(step_run_ref->>'resourceId'),attempt,created_at DESC)"
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM aip_responsibility_successor LIMIT 1)
          OR EXISTS (SELECT 1 FROM aip_takeover_request LIMIT 1)
          OR EXISTS (SELECT 1 FROM aip_takeover_decision_revision LIMIT 1)
          OR EXISTS (SELECT 1 FROM aip_execution_assignment_head LIMIT 1) THEN
          RAISE EXCEPTION 'cannot downgrade w3_016 with canonical assignment authority data'
            USING ERRCODE='55000';
        END IF;
        END $$"""
    )
    op.execute("DROP TABLE aip_takeover_decision_revision CASCADE")
    op.execute("DROP TABLE aip_execution_assignment_head CASCADE")
    op.execute("DROP TABLE aip_takeover_request CASCADE")
    op.execute("DROP TABLE aip_responsibility_successor CASCADE")
