"""Subordinate runtime authority; additive, never executed by registration."""
from alembic import op

revision = "ar1_001"
down_revision = "r5_d02_001"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "extension_runtime_binding", "extension_runtime_operation", "extension_runtime_event",
    "extension_runtime_outbox", "extension_runtime_dependency_ref",
    "extension_runtime_resource_lease", "extension_audit_envelope",
)


def upgrade():
    op.execute("""
    CREATE TABLE extension_runtime_binding (
      org_id text NOT NULL, project_id text NOT NULL, installation_id uuid NOT NULL,
      generation uuid NOT NULL, installation_revision bigint NOT NULL CHECK (installation_revision>0),
      package_lock_ref jsonb NOT NULL CHECK(jsonb_typeof(package_lock_ref)='object'),
      profile_ref text NOT NULL, config_ref jsonb,
      execution_epoch bigint NOT NULL DEFAULT 1 CHECK(execution_epoch>0),
      desired_state text NOT NULL CHECK(desired_state IN ('prepared','disabled','enabled','uninstalled')),
      observed_state text NOT NULL CHECK(observed_state IN ('preparing','ready','draining','stopped','unknown')),
      enabled boolean NOT NULL DEFAULT false, operation_fence boolean NOT NULL DEFAULT true,
      resource_handle_ref jsonb, revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      PRIMARY KEY(org_id,project_id,installation_id,generation),
      FOREIGN KEY(org_id,project_id,installation_id)
        REFERENCES bundle_installation(org_id,project_id,installation_id),
      CHECK(NOT enabled OR (observed_state='ready' AND NOT operation_fence AND config_ref IS NOT NULL))
    );
    CREATE TABLE extension_runtime_operation (
      org_id text NOT NULL, project_id text NOT NULL, operation_id uuid NOT NULL,
      installation_id uuid NOT NULL, kind text NOT NULL,
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 240),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      requested_by text NOT NULL, approved_by text, approval_ref jsonb,
      expected_installation_etag bigint NOT NULL CHECK(expected_installation_etag>0),
      expected_binding_revision bigint CHECK(expected_binding_revision>0),
      status text NOT NULL CHECK(status IN ('pending_approval','accepted','running','waiting_external','needs_attention','succeeded','failed','cancelled')),
      phase text NOT NULL, revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      deadline timestamptz NOT NULL, failure_code text, created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,operation_id),
      UNIQUE(org_id,project_id,installation_id,kind,idempotency_key),
      FOREIGN KEY(org_id,project_id,installation_id)
        REFERENCES bundle_installation(org_id,project_id,installation_id),
      CHECK(approved_by IS NULL OR approved_by<>requested_by)
    );
    CREATE TABLE extension_runtime_event (
      org_id text NOT NULL, project_id text NOT NULL, operation_id uuid NOT NULL,
      sequence bigint NOT NULL CHECK(sequence>0), event_id uuid NOT NULL UNIQUE,
      type text NOT NULL, payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      payload_hash text NOT NULL CHECK(payload_hash ~ '^sha256:[0-9a-f]{64}$'),
      occurred_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,operation_id,sequence),
      UNIQUE(org_id,project_id,event_id),
      FOREIGN KEY(org_id,project_id,operation_id)
        REFERENCES extension_runtime_operation(org_id,project_id,operation_id)
    );
    CREATE TABLE extension_runtime_outbox (
      org_id text NOT NULL, project_id text NOT NULL, event_id uuid NOT NULL,
      consumer_id text NOT NULL, attempt integer NOT NULL DEFAULT 0 CHECK(attempt>=0),
      next_attempt timestamptz NOT NULL DEFAULT now(), claim_until timestamptz, delivered_at timestamptz,
      PRIMARY KEY(org_id,project_id,event_id,consumer_id),
      FOREIGN KEY(org_id,project_id,event_id) REFERENCES extension_runtime_event(org_id,project_id,event_id)
    );
    CREATE TABLE extension_runtime_dependency_ref (
      org_id text NOT NULL, project_id text NOT NULL,
      consumer_installation uuid NOT NULL, consumer_generation uuid NOT NULL,
      provider_installation uuid NOT NULL, provider_generation uuid NOT NULL,
      kind text NOT NULL CHECK(kind IN ('capability','data','reconcile')),
      active boolean NOT NULL DEFAULT true, revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      PRIMARY KEY(org_id,project_id,consumer_installation,consumer_generation,provider_installation,provider_generation,kind),
      FOREIGN KEY(org_id,project_id,consumer_installation,consumer_generation)
        REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation),
      FOREIGN KEY(org_id,project_id,provider_installation,provider_generation)
        REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation)
    );
    CREATE TABLE extension_runtime_resource_lease (
      org_id text NOT NULL, project_id text NOT NULL, resource_id uuid NOT NULL,
      operation_id uuid NOT NULL, owner_token_ref text NOT NULL,
      generation uuid NOT NULL, package_id text NOT NULL,
      package_hash text NOT NULL CHECK(package_hash ~ '^sha256:[0-9a-f]{64}$'),
      engine_context text NOT NULL, resource_name text NOT NULL, container_id text,
      create_claimed_at timestamptz,
      cleanup_state text NOT NULL DEFAULT 'pending' CHECK(cleanup_state IN ('pending','uncertain','released')),
      expires_at timestamptz NOT NULL, observed_release boolean NOT NULL DEFAULT false,
      PRIMARY KEY(org_id,project_id,resource_id),
      UNIQUE(org_id,project_id,operation_id,generation,package_id,package_hash),
      UNIQUE(engine_context,resource_name),
      FOREIGN KEY(org_id,project_id,operation_id)
        REFERENCES extension_runtime_operation(org_id,project_id,operation_id)
    );
    CREATE TABLE extension_schema_installation (
      package_id text NOT NULL, schema_version text NOT NULL,
      migration_hash text NOT NULL CHECK(migration_hash ~ '^sha256:[0-9a-f]{64}$'),
      applied_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(package_id,schema_version), UNIQUE(package_id,schema_version,migration_hash)
    );
    CREATE TABLE extension_audit_envelope (
      org_id text NOT NULL, project_id text NOT NULL, envelope_id uuid NOT NULL,
      installation_id uuid NOT NULL, business_title text NOT NULL CHECK(length(business_title) BETWEEN 1 AND 240),
      envelope jsonb NOT NULL CHECK(jsonb_typeof(envelope)='object'),
      source_receipt_ref jsonb NOT NULL CHECK(jsonb_typeof(source_receipt_ref)='object'),
      occurred_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,envelope_id),
      FOREIGN KEY(org_id,project_id,installation_id)
        REFERENCES bundle_installation(org_id,project_id,installation_id)
    );
    CREATE FUNCTION extension_reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'extension history is immutable'; END
    $$;
    """)
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        predicate = "org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)"
        op.execute(f"CREATE POLICY tenant_scope ON {table} USING ({predicate}) WITH CHECK ({predicate})")
    for table in ("extension_runtime_event", "extension_audit_envelope", "extension_schema_installation"):
        op.execute(f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation()")
    for table in TENANT_TABLES:
        privileges="SELECT,INSERT" if table in {"extension_runtime_event","extension_audit_envelope"} else "SELECT,INSERT,UPDATE"
        op.execute(f"GRANT {privileges} ON {table} TO aos_runtime")
    op.execute("GRANT SELECT ON extension_schema_installation TO aos_runtime")


def downgrade():
    raise RuntimeError("runtime authority must be retained; destructive downgrade is not supported")
