"""Immutable withdrawal receipt storage only; no withdrawal execution grant."""
from alembic import op

revision='a0v_029'
down_revision='a0v_028'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''CREATE TABLE extension_dispatch_withdrawal_receipt (
      org_id text NOT NULL, project_id text NOT NULL, receipt_id uuid NOT NULL,
      registration_receipt_id uuid NOT NULL,
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160 AND idempotency_key=btrim(idempotency_key)),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,idempotency_key),
      UNIQUE(org_id,project_id,registration_receipt_id),
      FOREIGN KEY(org_id,project_id,registration_receipt_id)
        REFERENCES extension_dispatch_registration_receipt(org_id,project_id,receipt_id)
    );
    ALTER TABLE extension_dispatch_withdrawal_receipt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_dispatch_withdrawal_receipt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_dispatch_withdrawal_receipt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE FUNCTION extension_dispatch_withdrawal_guard_a0v_029() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_origin record; v_ref jsonb; v_request jsonb;
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'withdrawal history is immutable' USING ERRCODE='55000';
      END IF;
      SELECT * INTO v_origin FROM public.extension_dispatch_registration_receipt
        WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND receipt_id=NEW.registration_receipt_id;
      IF NOT FOUND THEN RAISE EXCEPTION 'withdrawal origin unavailable' USING ERRCODE='23503'; END IF;
      v_ref:=jsonb_build_object('resourceType','FirstDispatchRegistrationReceipt',
        'resourceId',v_origin.receipt_id::text,'revision',1,'contentHash',v_origin.content_hash);
      v_request:=NEW.payload->'request';
      IF NEW.payload->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.first-dispatch-withdrawal-receipt/v1'
        OR NEW.payload-ARRAY['schemaVersion','tenant','receiptId','registrationReceiptRef','installationId',
            'generation','groupId','idempotencyKey','requestHash','actor','request','oldDispatchSnapshot',
            'releasedOperationCount','executable','createdAt'] <> '{}'::jsonb
        OR NEW.payload->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id)
        OR NEW.payload->>'receiptId' IS DISTINCT FROM NEW.receipt_id::text
        OR NEW.payload->'registrationReceiptRef' IS DISTINCT FROM v_ref
        OR NEW.payload->>'installationId' IS DISTINCT FROM v_origin.installation_id::text
        OR NEW.payload->>'generation' IS DISTINCT FROM v_origin.generation::text
        OR NEW.payload->>'groupId' IS DISTINCT FROM v_origin.group_id::text
        OR jsonb_typeof(NEW.payload->'idempotencyKey') IS DISTINCT FROM 'string'
        OR NEW.payload->>'idempotencyKey' IS DISTINCT FROM NEW.idempotency_key
        OR NEW.idempotency_key ~ '[[:cntrl:]]'
        OR NEW.payload->>'requestHash' IS DISTINCT FROM NEW.request_hash
        OR jsonb_typeof(NEW.payload->'actor') IS DISTINCT FROM 'string'
        OR length(NEW.payload->>'actor') NOT BETWEEN 1 AND 240
        OR NEW.payload->>'actor' <> btrim(NEW.payload->>'actor')
        OR NEW.payload->>'actor' ~ '[[:cntrl:]]'
        OR jsonb_typeof(NEW.payload->'oldDispatchSnapshot') IS DISTINCT FROM 'array'
        OR NEW.payload->'oldDispatchSnapshot' IS DISTINCT FROM v_origin.payload->'dispatchSnapshot'
        OR jsonb_array_length(NEW.payload->'oldDispatchSnapshot') IS DISTINCT FROM 9
        OR NEW.payload->'releasedOperationCount' IS DISTINCT FROM '9'::jsonb
        OR NEW.payload->'executable' IS DISTINCT FROM 'false'::jsonb
        OR jsonb_typeof(NEW.payload->'createdAt') IS DISTINCT FROM 'string'
        OR jsonb_typeof(v_request) IS DISTINCT FROM 'object'
        OR v_request-ARRAY['schemaVersion','registrationReceiptRef','expectedInstallationEtag','idempotencyKey'] <> '{}'::jsonb
        OR v_request->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.first-dispatch-withdrawal/v1'
        OR v_request->'registrationReceiptRef' IS DISTINCT FROM v_ref
        OR jsonb_typeof(v_request->'idempotencyKey') IS DISTINCT FROM 'string'
        OR v_request->>'idempotencyKey' IS DISTINCT FROM NEW.idempotency_key
        OR jsonb_typeof(v_request->'expectedInstallationEtag') IS DISTINCT FROM 'number'
        OR coalesce((v_request->'expectedInstallationEtag')::text,'') !~ '^[1-9][0-9]*$'
        OR NEW.request_hash IS DISTINCT FROM 'sha256:' || encode(public.digest(
            convert_to(public.canonical_asset_registry_jsonb(v_request),'UTF8'),'sha256'),'hex')
        OR NEW.content_hash IS DISTINCT FROM 'sha256:' || encode(public.digest(
            convert_to(public.canonical_asset_registry_jsonb(NEW.payload),'UTF8'),'sha256'),'hex')
      THEN RAISE EXCEPTION 'withdrawal receipt integrity differs' USING ERRCODE='23514'; END IF;
      IF (v_request->>'expectedInstallationEtag')::numeric > 9223372036854775807
      THEN RAISE EXCEPTION 'withdrawal revision out of range' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER immutable_history BEFORE INSERT OR UPDATE OR DELETE ON extension_dispatch_withdrawal_receipt
      FOR EACH ROW EXECUTE FUNCTION extension_dispatch_withdrawal_guard_a0v_029();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON extension_dispatch_withdrawal_receipt
      FOR EACH STATEMENT EXECUTE FUNCTION extension_dispatch_withdrawal_guard_a0v_029();
    REVOKE ALL ON extension_dispatch_withdrawal_receipt FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT SELECT ON extension_dispatch_withdrawal_receipt TO aos_runtime;
    REVOKE ALL ON FUNCTION extension_dispatch_withdrawal_guard_a0v_029() FROM PUBLIC;
    ''')


def downgrade():
    raise RuntimeError('withdrawal and registration history must be retained')
