"""Add investigation data-handling bindings and receipts. Revision ID: biw3_006."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw3_006"
down_revision: str | Sequence[str] | None = "biw3_005"
branch_labels = depends_on = None
SIGNATURE = "(text,text,text,jsonb)"


def upgrade() -> None:
    op.execute("""CREATE FUNCTION guard_investigation_data_handling_biw3_006() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'INVESTIGATION_DATA_HANDLING_IMMUTABLE' USING ERRCODE='55000';END $$""")
    op.execute("""CREATE TABLE business_investigation_data_handling_binding_revision(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,binding_id TEXT NOT NULL,revision BIGINT NOT NULL,
      content_hash TEXT NOT NULL,status TEXT NOT NULL,retention_policy_id TEXT NOT NULL,
      retention_policy_revision INTEGER NOT NULL,idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,
      authority_data JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,binding_id,revision),UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,retention_policy_id,retention_policy_revision)
        REFERENCES ontology_retention_policy_revision(org_id,workspace_id,record_id,revision),
      CHECK(revision=1),CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(status IN('active','blocked','unknown')))""")
    op.execute("""CREATE TABLE business_investigation_redaction_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,redaction_id TEXT NOT NULL,binding_id TEXT NOT NULL,
      binding_revision BIGINT NOT NULL,content_hash TEXT NOT NULL,status TEXT NOT NULL,
      raw_body_persisted BOOLEAN NOT NULL,download_allowed BOOLEAN NOT NULL,
      idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,authority_data JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(org_id,project_id,redaction_id),
      UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,binding_id,binding_revision)
        REFERENCES business_investigation_data_handling_binding_revision(org_id,project_id,binding_id,revision),
      CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(status IN('safe','quarantined','blocked','unknown')),CHECK(raw_body_persisted=false),CHECK(download_allowed=false))""")
    op.execute("""CREATE TABLE business_investigation_retention_disposition_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,disposition_id TEXT NOT NULL,binding_id TEXT NOT NULL,
      binding_revision BIGINT NOT NULL,content_hash TEXT NOT NULL,disposition TEXT NOT NULL,
      retained_content_hash TEXT NOT NULL,idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,
      authority_data JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,disposition_id),UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,binding_id,binding_revision)
        REFERENCES business_investigation_data_handling_binding_revision(org_id,project_id,binding_id,revision),
      CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(retained_content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(disposition IN('retain_redacted','quarantine','delete_content_keep_hash','blocked','unknown')))""")
    tables = (
        "business_investigation_data_handling_binding_revision",
        "business_investigation_redaction_receipt",
        "business_investigation_retention_disposition_receipt",
    )
    for table in tables:
        op.execute(f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_investigation_data_handling_biw3_006()")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_biw3_006 ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")

    op.execute("""CREATE FUNCTION investigation_data_handling_bind_biw3_006(p_binding_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_existing record;v_policy record;v_subject jsonb;v_found boolean;
      BEGIN
        SELECT b.authority_data,b.request_hash INTO v_existing FROM business_investigation_data_handling_binding_revision b
          WHERE b.org_id=v_org AND b.project_id=v_project AND b.idempotency_key=p_idempotency_key;
        IF FOUND THEN IF v_existing.request_hash<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='data-handling binding idempotency conflict';END IF;RETURN QUERY SELECT v_existing.authority_data,true;RETURN;END IF;
        IF v_org IS NULL OR v_project IS NULL OR p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'bindingId'<>p_binding_id OR p_payload->>'requestHash'<>p_request_hash
          OR p_payload->>'schemaVersion'<>'aos.business-investigation.data-handling-binding/v1' OR (p_payload->>'revision')::bigint<>1
          OR p_payload#>>'{markingPolicyRef,resourceType}'<>'DataMarkingPolicyRevision'
          OR p_payload#>>'{purposePolicyRef,resourceType}'<>'PurposePolicyRevision'
          OR p_payload#>>'{minimumPopulationPolicyRef,resourceType}'<>'MinimumPopulationPolicyRevision'
          OR p_payload#>>'{secretHandlingPolicyRef,resourceType}'<>'SecretHandlingPolicyRevision'
          OR p_payload#>>'{retentionPolicyRef,resourceType}'<>'OntologyRetentionPolicyRevision'
          OR COALESCE((p_payload->>'customerOrderDetailAllowed')::boolean,true)
          OR COALESCE((p_payload->>'downloadAllowed')::boolean,true)
          OR p_payload-ARRAY['schemaVersion','tenant','bindingId','revision','contentHash','subjectRefs','markingPolicyRef','purposePolicyRef','minimumPopulationPolicyRef','secretHandlingPolicyRef','retentionPolicyRef','domMode','screenshotMode','logMode','sampleMode','exportMode','customerOrderDetailAllowed','downloadAllowed','status','blockers','idempotencyKey','requestHash','createdBy','createdAt']<>'{}'::jsonb
          OR ((p_payload->>'status')='active' AND jsonb_array_length(p_payload->'blockers')<>0)
          OR ((p_payload->>'status')<>'active' AND jsonb_array_length(p_payload->'blockers')=0)
          OR p_payload ?| ARRAY['rawPayload','sampleValues','rawBody','html','dom','screenshotBody','pii','secret','token','cookie','password','dsn','providerBody']
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='data-handling binding violates security contract';END IF;
        IF EXISTS(SELECT 1 FROM jsonb_each_text(jsonb_build_object('dom',p_payload->>'domMode','screenshot',p_payload->>'screenshotMode','log',p_payload->>'logMode','sample',p_payload->>'sampleMode','export',p_payload->>'exportMode')) m WHERE m.value NOT IN('redacted_only','blocked'))
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='restricted raw artifact mode is not authorized';END IF;
        SELECT r.*,h.active_revision,h.archived_at INTO v_policy FROM ontology_retention_policy_revision r
          JOIN ontology_retention_policy_head h USING(org_id,workspace_id,record_id)
          WHERE r.org_id=v_org AND r.workspace_id=v_project AND r.record_id=p_payload#>>'{retentionPolicyRef,resourceId}'
            AND r.revision=(p_payload#>>'{retentionPolicyRef,revision}')::integer
            AND ('sha256:'||r.payload_hash)=p_payload#>>'{retentionPolicyRef,contentHash}' FOR SHARE OF r,h;
        IF v_policy IS NULL OR v_policy.archived_at IS NOT NULL OR v_policy.active_revision<>v_policy.revision
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='current exact retention policy is required';END IF;
        FOR v_subject IN SELECT value FROM jsonb_array_elements(p_payload->'subjectRefs') LOOP
          v_found:=false;
          IF v_subject->>'resourceType'='ObservationReceipt' THEN
            SELECT EXISTS(SELECT 1 FROM business_investigation_observation_receipt r WHERE r.org_id=v_org AND r.project_id=v_project AND r.receipt_id=v_subject->>'resourceId' AND r.content_hash=v_subject->>'contentHash') INTO v_found;
          ELSIF v_subject->>'resourceType'='SemanticHydrationReceipt' THEN
            SELECT EXISTS(SELECT 1 FROM business_investigation_semantic_hydration_receipt r WHERE r.org_id=v_org AND r.project_id=v_project AND r.hydration_id=v_subject->>'resourceId' AND r.content_hash=v_subject->>'contentHash') INTO v_found;
          END IF;
          IF NOT v_found OR (v_subject->>'revision')::integer<>1 THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='exact investigation subject authority is required';END IF;
        END LOOP;
        INSERT INTO business_investigation_data_handling_binding_revision(org_id,project_id,binding_id,revision,content_hash,status,retention_policy_id,retention_policy_revision,idempotency_key,request_hash,authority_data)
        VALUES(v_org,v_project,p_binding_id,1,p_payload->>'contentHash',p_payload->>'status',v_policy.record_id,v_policy.revision,p_idempotency_key,p_request_hash,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute("""CREATE FUNCTION investigation_redaction_record_biw3_006(p_redaction_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;v_binding record;
      BEGIN
        SELECT r.authority_data,r.request_hash INTO v_existing FROM business_investigation_redaction_receipt r WHERE r.org_id=v_org AND r.project_id=v_project AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN IF v_existing.request_hash<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='redaction receipt idempotency conflict';END IF;RETURN QUERY SELECT v_existing.authority_data,true;RETURN;END IF;
        SELECT b.* INTO v_binding FROM business_investigation_data_handling_binding_revision b WHERE b.org_id=v_org AND b.project_id=v_project
          AND b.binding_id=p_payload#>>'{bindingRef,resourceId}' AND b.revision=(p_payload#>>'{bindingRef,revision}')::bigint AND b.content_hash=p_payload#>>'{bindingRef,contentHash}' FOR SHARE;
        IF v_binding IS NULL OR v_binding.status<>'active' OR p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'redactionId'<>p_redaction_id OR p_payload->>'requestHash'<>p_request_hash
          OR p_payload->>'schemaVersion'<>'aos.business-investigation.redaction-receipt/v1'
          OR p_payload-ARRAY['schemaVersion','tenant','redactionId','contentHash','bindingRef','inputArtifactRef','outputArtifactRef','scannerRef','markingPolicyRef','retentionPolicyRef','status','categoryCounts','redactedFieldPaths','rawBodyPersisted','downloadAllowed','inspectedAt','blockers','idempotencyKey','requestHash','createdBy']<>'{}'::jsonb
          OR p_payload->>'rawBodyPersisted'<>'false' OR p_payload->>'downloadAllowed'<>'false'
          OR p_payload#>>'{inputArtifactRef,resourceType}' NOT IN('PageScreenshotArtifactRevision','DOMSnapshotArtifactRevision','ReadOnlyExportArtifactRevision','HydrationArtifactRevision','EvidenceArtifactRevision')
          OR p_payload#>>'{scannerRef,resourceType}'<>'SensitiveDataScannerRevision'
          OR EXISTS(SELECT 1 FROM jsonb_each_text(p_payload->'categoryCounts') c WHERE c.key NOT IN('pii','secret','token','cookie','password','dsn','provider_body','raw_sample') OR c.value !~ '^[0-9]+$')
          OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(p_payload->'redactedFieldPaths') f WHERE f !~ '^[A-Za-z_][A-Za-z0-9_.-]{0,199}$')
          OR p_payload->'markingPolicyRef'<>v_binding.authority_data->'markingPolicyRef'
          OR p_payload->'retentionPolicyRef'<>v_binding.authority_data->'retentionPolicyRef'
          OR ((p_payload->>'status')='safe' AND (NOT p_payload ? 'outputArtifactRef' OR p_payload->'outputArtifactRef'='null'::jsonb OR p_payload#>>'{outputArtifactRef,resourceType}'<>'RedactedArtifactRevision' OR jsonb_array_length(p_payload->'blockers')<>0))
          OR ((p_payload->>'status')<>'safe' AND jsonb_array_length(p_payload->'blockers')=0)
          OR p_payload ?| ARRAY['rawPayload','sampleValues','rawBody','html','dom','screenshotBody','pii','secret','token','cookie','password','dsn','providerBody']
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='redaction receipt violates exact safe-output contract';END IF;
        INSERT INTO business_investigation_redaction_receipt(org_id,project_id,redaction_id,binding_id,binding_revision,content_hash,status,raw_body_persisted,download_allowed,idempotency_key,request_hash,authority_data)
        VALUES(v_org,v_project,p_redaction_id,v_binding.binding_id,v_binding.revision,p_payload->>'contentHash',p_payload->>'status',false,false,p_idempotency_key,p_request_hash,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute("""CREATE FUNCTION investigation_retention_record_biw3_006(p_disposition_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;v_binding record;
      BEGIN
        SELECT r.authority_data,r.request_hash INTO v_existing FROM business_investigation_retention_disposition_receipt r WHERE r.org_id=v_org AND r.project_id=v_project AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN IF v_existing.request_hash<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='retention receipt idempotency conflict';END IF;RETURN QUERY SELECT v_existing.authority_data,true;RETURN;END IF;
        SELECT b.* INTO v_binding FROM business_investigation_data_handling_binding_revision b WHERE b.org_id=v_org AND b.project_id=v_project
          AND b.binding_id=p_payload#>>'{bindingRef,resourceId}' AND b.revision=(p_payload#>>'{bindingRef,revision}')::bigint AND b.content_hash=p_payload#>>'{bindingRef,contentHash}' FOR SHARE;
        IF v_binding IS NULL OR p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'dispositionId'<>p_disposition_id OR p_payload->>'requestHash'<>p_request_hash
          OR p_payload->>'schemaVersion'<>'aos.business-investigation.retention-disposition-receipt/v1'
          OR p_payload-ARRAY['schemaVersion','tenant','dispositionId','contentHash','bindingRef','artifactRef','retentionPolicyRef','disposition','retainedContentHash','cleanupReceiptRef','dueAt','decidedAt','blockers','idempotencyKey','requestHash','createdBy']<>'{}'::jsonb
          OR p_payload#>>'{artifactRef,resourceType}'<>'RedactedArtifactRevision'
          OR p_payload->>'retainedContentHash' !~ '^sha256:[0-9a-f]{64}$'
          OR p_payload->'retentionPolicyRef'<>v_binding.authority_data->'retentionPolicyRef'
          OR ((p_payload->>'disposition')='delete_content_keep_hash' AND p_payload#>>'{cleanupReceiptRef,resourceType}'<>'OntologyEvidenceCleanupReceipt')
          OR ((p_payload->>'disposition')='delete_content_keep_hash' AND NOT EXISTS(
            SELECT 1 FROM ontology_evidence_cleanup_receipt c WHERE c.org_id=v_org AND c.workspace_id=v_project
              AND c.cleanup_id::text=p_payload#>>'{cleanupReceiptRef,resourceId}'
              AND ('sha256:'||c.content_hash)=p_payload#>>'{cleanupReceiptRef,contentHash}'))
          OR ((p_payload->>'disposition') IN('blocked','unknown') AND jsonb_array_length(p_payload->'blockers')=0)
          OR ((p_payload->>'disposition') NOT IN('blocked','unknown') AND jsonb_array_length(p_payload->'blockers')<>0)
          OR ((p_payload->>'disposition')='retain_redacted' AND (p_payload->>'decidedAt')::timestamptz>(p_payload->>'dueAt')::timestamptz)
          OR p_payload ?| ARRAY['rawPayload','sampleValues','rawBody','html','dom','screenshotBody','pii','secret','token','cookie','password','dsn','providerBody']
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='retention disposition violates exact receipt contract';END IF;
        INSERT INTO business_investigation_retention_disposition_receipt(org_id,project_id,disposition_id,binding_id,binding_revision,content_hash,disposition,retained_content_hash,idempotency_key,request_hash,authority_data)
        VALUES(v_org,v_project,p_disposition_id,v_binding.binding_id,v_binding.revision,p_payload->>'contentHash',p_payload->>'disposition',p_payload->>'retainedContentHash',p_idempotency_key,p_request_hash,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    for name in (
        "investigation_data_handling_bind_biw3_006",
        "investigation_redaction_record_biw3_006",
        "investigation_retention_record_biw3_006",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {name}{SIGNATURE} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {name}{SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM business_investigation_data_handling_binding_revision LIMIT 1)
      OR EXISTS(SELECT 1 FROM business_investigation_redaction_receipt LIMIT 1)
      OR EXISTS(SELECT 1 FROM business_investigation_retention_disposition_receipt LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw3_006 with data-handling authority' USING ERRCODE='55000';END IF;END $$""")
    for name in (
        "investigation_retention_record_biw3_006",
        "investigation_redaction_record_biw3_006",
        "investigation_data_handling_bind_biw3_006",
    ):
        op.execute(f"DROP FUNCTION {name}{SIGNATURE}")
    op.execute("DROP TABLE business_investigation_retention_disposition_receipt")
    op.execute("DROP TABLE business_investigation_redaction_receipt")
    op.execute("DROP TABLE business_investigation_data_handling_binding_revision")
    op.execute("DROP FUNCTION guard_investigation_data_handling_biw3_006()")
