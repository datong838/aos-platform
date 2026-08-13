"""Add canonical AIP agent, skill and handoff authority.

Revision ID: aip6_001
Revises: aip5_004
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip6_001"
down_revision: str | Sequence[str] | None = "aip5_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCOPED = (
    "aip_agent_instance",
    "aip_skill_binding",
    "aip_capability_binding",
    "aip_agent_run",
    "aip_handoff_envelope",
    "aip_handoff_event",
)
_APPEND_ONLY = (
    "aip_agent_template_revision",
    "aip_skill_template_revision",
    "aip_handoff_event",
)


def _scope(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_aip6 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_agent_template_revision (
          template_id TEXT NOT NULL, revision BIGINT NOT NULL,
          display_name TEXT NOT NULL, role_key TEXT NOT NULL,
          lifecycle TEXT NOT NULL, source_ref JSONB NOT NULL,
          source_license TEXT NOT NULL, manifest JSONB NOT NULL,
          content_hash TEXT NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (template_id,revision),
          UNIQUE (template_id,content_hash),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (lifecycle IN ('draft','evaluated','published','deprecated','revoked')),
          CHECK (jsonb_typeof(source_ref)='object'),
          CHECK (jsonb_typeof(manifest)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_skill_template_revision (
          skill_id TEXT NOT NULL, revision BIGINT NOT NULL,
          canonical_logic_id TEXT NOT NULL, lifecycle TEXT NOT NULL,
          input_schema JSONB NOT NULL, output_schema JSONB NOT NULL,
          tool_allowlist JSONB NOT NULL, required_capabilities JSONB NOT NULL,
          risk_level TEXT NOT NULL, eval_pack_ref JSONB,
          memory_policy_ref JSONB NOT NULL, handoff_policy_ref JSONB NOT NULL,
          source_ref JSONB NOT NULL, source_license TEXT NOT NULL,
          content_hash TEXT NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (skill_id,revision),
          UNIQUE (canonical_logic_id,revision), UNIQUE (skill_id,content_hash),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (lifecycle IN ('draft','evaluated','published','deprecated','revoked')),
          CHECK (risk_level IN ('low','medium','high','critical')),
          CHECK (jsonb_typeof(input_schema)='object'),
          CHECK (jsonb_typeof(output_schema)='object'),
          CHECK (jsonb_typeof(tool_allowlist)='array'),
          CHECK (jsonb_typeof(required_capabilities)='array')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_agent_instance (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          instance_id TEXT NOT NULL, template_id TEXT NOT NULL,
          template_revision BIGINT NOT NULL, status TEXT NOT NULL,
          overlay JSONB NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,instance_id),
          CHECK (status IN ('provisioning','active','suspended','deleted')),
          CHECK (jsonb_typeof(overlay)='object'), CHECK (version >= 1),
          FOREIGN KEY (template_id,template_revision)
            REFERENCES aip_agent_template_revision(template_id,revision),
          FOREIGN KEY (org_id,project_id)
            REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_skill_binding (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          binding_id TEXT NOT NULL, instance_id TEXT NOT NULL,
          skill_id TEXT NOT NULL, skill_revision BIGINT NOT NULL,
          capability_refs JSONB NOT NULL, budget_policy_ref JSONB NOT NULL,
          status TEXT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,binding_id),
          UNIQUE (org_id,project_id,instance_id,skill_id,skill_revision),
          CHECK (status IN ('provisioning','active','suspended','revoked')),
          CHECK (jsonb_typeof(capability_refs)='array'), CHECK (version >= 1),
          FOREIGN KEY (skill_id,skill_revision)
            REFERENCES aip_skill_template_revision(skill_id,revision),
          FOREIGN KEY (org_id,project_id,instance_id)
            REFERENCES aip_agent_instance(org_id,project_id,instance_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_capability_binding (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          binding_id TEXT NOT NULL, capability_ref JSONB NOT NULL,
          secret_ref TEXT NOT NULL, health TEXT NOT NULL,
          network_policy_revision TEXT NOT NULL,
          quota_policy_revision TEXT NOT NULL,
          timeout_ms BIGINT NOT NULL, max_concurrency BIGINT NOT NULL,
          status TEXT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          observed_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,binding_id),
          CHECK (jsonb_typeof(capability_ref)='object'),
          CHECK (secret_ref ~ '^(vault|secret|keychain)://'),
          CHECK (health IN ('unknown','healthy','degraded','unavailable','revoked')),
          CHECK (status IN ('provisioning','active','suspended','revoked')),
          CHECK (timeout_ms BETWEEN 100 AND 3600000),
          CHECK (max_concurrency BETWEEN 1 AND 10000), CHECK (version >= 1),
          FOREIGN KEY (org_id,project_id)
            REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_agent_run (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          agent_run_id TEXT NOT NULL, task_id TEXT NOT NULL,
          task_run_id TEXT NOT NULL, plan_ref JSONB NOT NULL,
          instance_id TEXT NOT NULL, instance_version BIGINT NOT NULL,
          skill_binding_id TEXT NOT NULL, skill_ref JSONB NOT NULL,
          logic_ref JSONB NOT NULL, model_route_ref JSONB NOT NULL,
          policy_ref JSONB NOT NULL, input_refs JSONB NOT NULL,
          status TEXT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,agent_run_id),
          CHECK (status IN ('queued','running','paused','succeeded','failed','cancelled','unknown')),
          CHECK (instance_version >= 1), CHECK (version >= 1),
          CHECK (jsonb_typeof(input_refs)='array'),
          FOREIGN KEY (org_id,project_id,task_id)
            REFERENCES aip_task(org_id,project_id,task_id),
          FOREIGN KEY (org_id,project_id,task_run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY (org_id,project_id,instance_id)
            REFERENCES aip_agent_instance(org_id,project_id,instance_id),
          FOREIGN KEY (org_id,project_id,skill_binding_id)
            REFERENCES aip_skill_binding(org_id,project_id,binding_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_handoff_envelope (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          handoff_id TEXT NOT NULL, task_id TEXT NOT NULL,
          task_run_id TEXT NOT NULL, sender_instance_id TEXT NOT NULL,
          receiver_instance_id TEXT NOT NULL, object_refs JSONB NOT NULL,
          artifact_refs JSONB NOT NULL, evidence_refs JSONB NOT NULL,
          context_payload JSONB NOT NULL, allowed_context_fields JSONB NOT NULL,
          markings JSONB NOT NULL, token_hash TEXT NOT NULL,
          status TEXT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,handoff_id),
          UNIQUE (org_id,project_id,token_hash),
          CHECK (token_hash ~ '^[0-9a-f]{64}$'),
          CHECK (status IN ('issued','consumed','expired','revoked')),
          CHECK (sender_instance_id <> receiver_instance_id),
          CHECK (jsonb_typeof(context_payload)='object'),
          CHECK (jsonb_typeof(allowed_context_fields)='array'),
          CHECK (jsonb_typeof(markings)='array' AND jsonb_array_length(markings)>0),
          CHECK (version >= 1),
          FOREIGN KEY (org_id,project_id,task_id)
            REFERENCES aip_task(org_id,project_id,task_id),
          FOREIGN KEY (org_id,project_id,task_run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY (org_id,project_id,sender_instance_id)
            REFERENCES aip_agent_instance(org_id,project_id,instance_id),
          FOREIGN KEY (org_id,project_id,receiver_instance_id)
            REFERENCES aip_agent_instance(org_id,project_id,instance_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_handoff_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          event_id TEXT NOT NULL, handoff_id TEXT NOT NULL,
          sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
          from_status TEXT, to_status TEXT NOT NULL,
          actor_ref JSONB NOT NULL, reason_code TEXT,
          event_hash TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,event_id),
          UNIQUE (org_id,project_id,handoff_id,sequence),
          CHECK (sequence >= 1), CHECK (event_hash ~ '^[0-9a-f]{64}$'),
          CHECK (event_type IN ('issued','consumed','expired','revoked')),
          CHECK (to_status IN ('issued','consumed','expired','revoked')),
          FOREIGN KEY (org_id,project_id,handoff_id)
            REFERENCES aip_handoff_envelope(org_id,project_id,handoff_id)
        )"""
    )

    for table in _SCOPED:
        _scope(table)

    op.execute(
        """CREATE FUNCTION guard_aip6_registry_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'AIP6_REGISTRY_APPEND_ONLY' USING ERRCODE='55000';
        END;
        $$ LANGUAGE plpgsql"""
    )
    for table in _APPEND_ONLY:
        op.execute(
            f"""CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip6_registry_append_only()"""
        )
        op.execute(
            f"""CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_aip6_registry_append_only()"""
        )

    for table in _SCOPED:
        if table == "aip_handoff_event":
            op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")
        else:
            op.execute(f"GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime")


def downgrade() -> None:
    for table in reversed(_SCOPED):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("DROP TABLE IF EXISTS aip_skill_template_revision")
    op.execute("DROP TABLE IF EXISTS aip_agent_template_revision")
    op.execute("DROP FUNCTION IF EXISTS guard_aip6_registry_append_only()")
