"""Read-only application ledger for future exact configuration continuation."""
from alembic import op
revision='a0v_067'
down_revision='a0v_066'
branch_labels=depends_on=None


def upgrade():
    op.execute('''
    CREATE TABLE extension_dispatch_configuration_refresh_receipt(
      org_id text NOT NULL,project_id text NOT NULL,cutover_group_id uuid NOT NULL,
      receipt_id uuid NOT NULL,revision bigint NOT NULL CHECK(revision>0),
      activation_operation_id uuid NOT NULL,activation_resume_receipt_id uuid NOT NULL,
      installation_id uuid NOT NULL,generation uuid NOT NULL,
      previous_receipt_id uuid,previous_hash text,
      actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240 AND actor=btrim(actor)),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160 AND idempotency_key=btrim(idempotency_key)),
      request jsonb NOT NULL CHECK(jsonb_typeof(request)='object' AND octet_length(request::text)<=16384),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      body jsonb NOT NULL CHECK(jsonb_typeof(body)='object' AND octet_length(body::text)<=32768),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id,cutover_group_id,revision),
      UNIQUE(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,receipt_id,content_hash),
      UNIQUE(org_id,project_id,cutover_group_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,activation_operation_id)
        REFERENCES extension_dispatch_cutover_operation(org_id,project_id,cutover_operation_id),
      FOREIGN KEY(org_id,project_id,activation_resume_receipt_id)
        REFERENCES extension_dispatch_cutover_receipt(org_id,project_id,receipt_id),
      FOREIGN KEY(org_id,project_id,previous_receipt_id,previous_hash)
        REFERENCES extension_dispatch_configuration_refresh_receipt(org_id,project_id,receipt_id,content_hash),
      CHECK((revision=1 AND previous_receipt_id IS NULL AND previous_hash IS NULL)
         OR (revision>1 AND previous_receipt_id IS NOT NULL AND previous_hash IS NOT NULL))
    );
    CREATE FUNCTION validate_dispatch_configuration_refresh_a0v_067() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE parent record; root record; activation record; source jsonb; expected jsonb;
    BEGIN
      IF (NEW.request_hash=public.canonical_bundle_control_sha256(NEW.request)
          AND NEW.content_hash=public.canonical_bundle_control_sha256(NEW.body)
          AND NEW.request->>'schemaVersion'='aos.ecommerce.dispatch-configuration-refresh/v1'
          AND NEW.request->>'orgId'=NEW.org_id AND NEW.request->>'projectId'=NEW.project_id
          AND NEW.request->>'cutoverGroupId'=NEW.cutover_group_id::text
          AND NEW.request->>'generation'=NEW.generation::text
          AND NEW.request->'installationRef'->>'installationId'=NEW.installation_id::text
          AND NEW.request->>'idempotencyKey'=NEW.idempotency_key
          AND NEW.request->'externalEffectsAllowed'='false'::jsonb
          AND NEW.request->'resumeBusinessRuns'='false'::jsonb) IS NOT TRUE
      THEN RAISE EXCEPTION 'refresh request projection differs' USING ERRCODE='23514'; END IF;
      expected:=jsonb_build_object('schemaVersion','aos.ecommerce.dispatch-configuration-refresh-receipt/v1',
        'receiptId',NEW.receipt_id::text,'revision',NEW.revision,
        'activationOperationId',NEW.activation_operation_id::text,
        'activationResumeReceiptId',NEW.activation_resume_receipt_id::text,
        'actor',NEW.actor,'request',NEW.request,'requestHash',NEW.request_hash,'createdAt',NEW.body->>'createdAt');
      IF (NEW.body=expected AND (NEW.body->>'createdAt')::timestamptz=NEW.created_at
          AND NEW.body->>'createdAt' ~ '[+]00:00$') IS NOT TRUE
      THEN RAISE EXCEPTION 'refresh body projection differs' USING ERRCODE='23514'; END IF;
      SELECT * INTO root FROM public.extension_dispatch_cutover_receipt
        WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND receipt_id=NEW.activation_resume_receipt_id;
      IF NOT FOUND OR root.phase<>'resume' OR root.cutover_operation_id<>NEW.activation_operation_id
      THEN RAISE EXCEPTION 'original resumed activation required' USING ERRCODE='23514'; END IF;
      SELECT * INTO activation FROM public.extension_dispatch_cutover_operation
        WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND cutover_operation_id=NEW.activation_operation_id;
      IF NOT FOUND OR activation.kind<>'activate' OR activation.cutover_group_id<>NEW.cutover_group_id
         OR activation.target_installation_id<>NEW.installation_id OR activation.target_generation<>NEW.generation
      THEN RAISE EXCEPTION 'refresh root target differs' USING ERRCODE='23514'; END IF;
      source:=NEW.request->'sourceAuthorityRef';
      IF NEW.revision=1 THEN
        expected:=jsonb_build_object('resourceType','CutoverResumeReceipt','resourceId',root.receipt_id::text,
          'revision',1,'contentHash',root.content_hash);
      ELSE
        SELECT * INTO parent FROM public.extension_dispatch_configuration_refresh_receipt
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND receipt_id=NEW.previous_receipt_id;
        IF NOT FOUND OR parent.revision<>NEW.revision-1 OR parent.cutover_group_id<>NEW.cutover_group_id
           OR parent.activation_operation_id<>NEW.activation_operation_id
           OR parent.activation_resume_receipt_id<>NEW.activation_resume_receipt_id
           OR parent.installation_id<>NEW.installation_id OR parent.generation<>NEW.generation
           OR parent.content_hash<>NEW.previous_hash
        THEN RAISE EXCEPTION 'refresh predecessor chain differs' USING ERRCODE='23514'; END IF;
        IF (NEW.request->'sourceRuntimeRevision'=parent.request->'targetRuntimeRevision'
            AND NEW.request->'sourceExecutionEpoch'=parent.request->'targetExecutionEpoch'
            AND NEW.request->'sourceConfigurationRef'=parent.request->'targetConfigurationRef'
            AND NEW.request->'expectedGroupRevision'=
              to_jsonb((parent.request->>'expectedGroupRevision')::bigint+1)) IS NOT TRUE
        THEN RAISE EXCEPTION 'refresh source must continue previous target' USING ERRCODE='23514'; END IF;
        expected:=jsonb_build_object('resourceType','DispatchConfigurationRefreshReceipt',
          'resourceId',parent.receipt_id::text,'revision',parent.revision,'contentHash',parent.content_hash);
      END IF;
      IF source IS DISTINCT FROM expected
      THEN RAISE EXCEPTION 'refresh predecessor ref differs' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER validate_refresh_history BEFORE INSERT ON extension_dispatch_configuration_refresh_receipt
      FOR EACH ROW EXECUTE FUNCTION validate_dispatch_configuration_refresh_a0v_067();
    CREATE TRIGGER immutable_refresh_history BEFORE UPDATE OR DELETE OR TRUNCATE ON extension_dispatch_configuration_refresh_receipt
      FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    ALTER TABLE extension_dispatch_configuration_refresh_receipt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_dispatch_configuration_refresh_receipt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_dispatch_configuration_refresh_receipt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON extension_dispatch_configuration_refresh_receipt FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT SELECT ON extension_dispatch_configuration_refresh_receipt TO aos_runtime,aos_extension_maintainer;
    REVOKE ALL ON FUNCTION validate_dispatch_configuration_refresh_a0v_067() FROM PUBLIC;
    ''')


def downgrade():raise RuntimeError('configuration continuation history must be retained')
