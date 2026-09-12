"""Immutable first-registration receipt; no registration write capability."""
from alembic import op

revision = 'a0v_026'
down_revision = 'a0v_025'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE extension_dispatch_registration_receipt (
        org_id text NOT NULL, project_id text NOT NULL,
        receipt_id uuid NOT NULL, installation_id uuid NOT NULL, generation uuid NOT NULL,
        group_id uuid NOT NULL,
        idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160 AND idempotency_key=btrim(idempotency_key)),
        request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,receipt_id),
        UNIQUE(org_id,project_id,idempotency_key),
        UNIQUE(org_id,project_id,group_id),
        FOREIGN KEY(org_id,project_id,installation_id,generation)
          REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation)
    );
    ALTER TABLE extension_dispatch_registration_receipt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_dispatch_registration_receipt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_dispatch_registration_receipt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE FUNCTION extension_dispatch_registration_guard_a0v_026() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'registration history is immutable' USING ERRCODE='55000';
      END IF;
      IF NEW.payload->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.first-dispatch-registration-receipt/v1'
        OR NEW.payload#>>'{tenant,orgId}' IS DISTINCT FROM NEW.org_id
        OR NEW.payload#>>'{tenant,projectId}' IS DISTINCT FROM NEW.project_id
        OR NEW.payload->>'receiptId' IS DISTINCT FROM NEW.receipt_id::text
        OR NEW.payload->>'installationId' IS DISTINCT FROM NEW.installation_id::text
        OR NEW.payload->>'generation' IS DISTINCT FROM NEW.generation::text
        OR NEW.payload->>'groupId' IS DISTINCT FROM NEW.group_id::text
        OR NEW.payload->>'idempotencyKey' IS DISTINCT FROM NEW.idempotency_key
        OR NEW.payload->>'requestHash' IS DISTINCT FROM NEW.request_hash
        OR NEW.content_hash IS DISTINCT FROM 'sha256:' || encode(public.digest(
            convert_to(public.canonical_asset_registry_jsonb(NEW.payload),'UTF8'),'sha256'),'hex')
      THEN RAISE EXCEPTION 'registration receipt integrity differs' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER immutable_history BEFORE INSERT OR UPDATE OR DELETE ON extension_dispatch_registration_receipt
      FOR EACH ROW EXECUTE FUNCTION extension_dispatch_registration_guard_a0v_026();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON extension_dispatch_registration_receipt
      FOR EACH STATEMENT EXECUTE FUNCTION extension_dispatch_registration_guard_a0v_026();
    REVOKE ALL ON extension_dispatch_registration_receipt FROM PUBLIC,aos_runtime;
    GRANT SELECT ON extension_dispatch_registration_receipt TO aos_runtime;
    REVOKE ALL ON FUNCTION extension_dispatch_registration_guard_a0v_026() FROM PUBLIC;
    ''')


def downgrade():
    raise RuntimeError('registration history must be retained')
