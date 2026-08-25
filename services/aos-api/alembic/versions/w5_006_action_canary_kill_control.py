"""Add canonical Action Kill policy, Canary plan and drill authorities.

Revision ID: w5_006
Revises: w5_005
"""
from __future__ import annotations

from alembic import op

revision = "w5_006"
down_revision = "w5_005"
branch_labels = None
depends_on = None


TENANT_TABLES = (
    "aip_action_kill_policy_revision",
    "aip_action_kill_policy_head",
    "aip_action_kill_policy_approval_event",
    "aip_action_kill_policy_command_receipt",
    "aip_action_canary_plan_revision",
    "aip_action_canary_plan_approval_event",
    "aip_action_kill_drill_receipt",
)


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_action_kill_policy_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, policy_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL, level TEXT NOT NULL,
          kill_enabled BOOLEAN NOT NULL, reason_code TEXT NOT NULL,
          account_binding_ref JSONB, adapter_revision_ref JSONB,
          capability_binding_ref JSONB, action_type_id TEXT,
          valid_from TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ,
          proposed_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,policy_id,revision),
          UNIQUE (org_id,project_id,policy_id,content_hash),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (level IN ('org','project','account','adapter','capability','action_type')),
          CHECK (expires_at IS NULL OR expires_at > valid_from),
          CHECK (account_binding_ref IS NULL OR jsonb_typeof(account_binding_ref)='object'),
          CHECK (adapter_revision_ref IS NULL OR jsonb_typeof(adapter_revision_ref)='object'),
          CHECK (capability_binding_ref IS NULL OR jsonb_typeof(capability_binding_ref)='object'),
          CHECK ((level='account')=(account_binding_ref IS NOT NULL)),
          CHECK ((level='adapter')=(adapter_revision_ref IS NOT NULL)),
          CHECK ((level='capability')=(capability_binding_ref IS NOT NULL)),
          CHECK ((level='action_type')=(action_type_id IS NOT NULL)),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_kill_policy_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, policy_id TEXT NOT NULL,
          active_revision BIGINT, version BIGINT NOT NULL DEFAULT 0,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,policy_id), CHECK (version >= 0),
          CHECK (active_revision IS NULL OR active_revision >= 1),
          FOREIGN KEY (org_id,project_id,policy_id,active_revision)
            REFERENCES aip_action_kill_policy_revision(org_id,project_id,policy_id,revision)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_kill_policy_approval_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, approval_event_id TEXT NOT NULL,
          policy_id TEXT NOT NULL, revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          decision TEXT NOT NULL, actor_id TEXT NOT NULL, reason TEXT NOT NULL,
          expected_head_version BIGINT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,approval_event_id),
          UNIQUE (org_id,project_id,policy_id,revision),
          CHECK (decision IN ('approved','rejected')),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'), CHECK (expected_head_version >= 0),
          FOREIGN KEY (org_id,project_id,policy_id,revision)
            REFERENCES aip_action_kill_policy_revision(org_id,project_id,policy_id,revision)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_kill_policy_command_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          command_type TEXT NOT NULL, idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL, result_ref JSONB NOT NULL,
          actor_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,receipt_id),
          UNIQUE (org_id,project_id,command_type,idempotency_key),
          CHECK (command_type IN ('propose','approve','reject')),
          CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(result_ref)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_canary_plan_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, plan_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          action_type_revision_ref JSONB NOT NULL, capability_binding_ref JSONB NOT NULL,
          account_binding_ref JSONB NOT NULL, adapter_revision_ref JSONB NOT NULL,
          object_ref JSONB NOT NULL, max_quantity BIGINT NOT NULL,
          max_budget NUMERIC(20,6) NOT NULL, currency TEXT NOT NULL,
          window_starts_at TIMESTAMPTZ NOT NULL, window_ends_at TIMESTAMPTZ NOT NULL,
          operator_id TEXT NOT NULL, stop_conditions JSONB NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          proposed_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,plan_id,revision),
          UNIQUE (org_id,project_id,plan_id,content_hash),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          CHECK (max_quantity BETWEEN 1 AND 10), CHECK (max_budget >= 0),
          CHECK (window_ends_at > window_starts_at),
          CHECK (jsonb_typeof(action_type_revision_ref)='object'),
          CHECK (jsonb_typeof(capability_binding_ref)='object'),
          CHECK (jsonb_typeof(account_binding_ref)='object'),
          CHECK (jsonb_typeof(adapter_revision_ref)='object'),
          CHECK (jsonb_typeof(object_ref)='object'),
          CHECK (jsonb_typeof(stop_conditions)='array'),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_canary_plan_approval_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, approval_event_id TEXT NOT NULL,
          plan_id TEXT NOT NULL, revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          decision TEXT NOT NULL, actor_id TEXT NOT NULL, reason TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,approval_event_id),
          UNIQUE (org_id,project_id,plan_id,revision,actor_id),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (decision IN ('approved','rejected')),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,plan_id,revision)
            REFERENCES aip_action_canary_plan_revision(org_id,project_id,plan_id,revision)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_kill_drill_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          policy_ref JSONB NOT NULL, simulation_only BOOLEAN NOT NULL DEFAULT TRUE,
          blocked_new_dispatches JSONB NOT NULL, inflight_reconcile_attempts JSONB NOT NULL,
          invariants JSONB NOT NULL, result TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          actor_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,receipt_id),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (simulation_only), CHECK (result IN ('passed','failed')),
          CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(policy_ref)='object'),
          CHECK (jsonb_typeof(blocked_new_dispatches)='array'),
          CHECK (jsonb_typeof(inflight_reconcile_attempts)='array'),
          CHECK (jsonb_typeof(invariants)='object')
        )"""
    )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table}_tenant_scope ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )
        privileges = "SELECT,INSERT,UPDATE" if table == "aip_action_kill_policy_head" else "SELECT,INSERT"
        op.execute(f"GRANT {privileges} ON {table} TO aos_runtime")
    for table in TENANT_TABLES:
        if table == "aip_action_kill_policy_head":
            continue
        op.execute(
            f"""CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
        )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_action_kill_policy_revision LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_action_canary_plan_revision LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_action_kill_drill_receipt LIMIT 1) THEN
            RAISE EXCEPTION 'W5_006_FACTS_EXIST';
          END IF;
        END $$"""
    )
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP TABLE {table}")
