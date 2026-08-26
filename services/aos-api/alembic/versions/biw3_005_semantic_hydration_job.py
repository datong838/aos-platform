"""Add receipt-first semantic hydration authority. Revision ID: biw3_005."""

from collections.abc import Sequence
from alembic import op

revision: str = "biw3_005"
down_revision: str | Sequence[str] | None = "biw3_004"
branch_labels = depends_on = None
REQUEST_SIGNATURE = "(text,text,text,jsonb)"
RECORD_SIGNATURE = "(text,text,text,jsonb)"


def upgrade() -> None:
    op.execute("""CREATE TABLE business_investigation_semantic_hydration_job_revision(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,hydration_job_id TEXT NOT NULL,revision BIGINT NOT NULL,
      content_hash TEXT NOT NULL,status TEXT NOT NULL,profile_id TEXT NOT NULL,profile_revision BIGINT NOT NULL,
      cutoff_at TIMESTAMPTZ NOT NULL,idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,
      authority_data JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,hydration_job_id,revision),UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,profile_id,profile_revision) REFERENCES business_investigation_adaptive_profile_revision(org_id,project_id,profile_id,revision),
      CHECK(revision=1),CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(status IN('requested','blocked','unknown')))""")
    op.execute("""CREATE TABLE business_investigation_semantic_hydration_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,hydration_id TEXT NOT NULL,hydration_job_id TEXT NOT NULL,
      hydration_job_revision BIGINT NOT NULL,content_hash TEXT NOT NULL,status TEXT NOT NULL,
      attempted BIGINT NOT NULL,created_count BIGINT NOT NULL,updated_count BIGINT NOT NULL,
      quarantined_count BIGINT NOT NULL,unknown_count BIGINT NOT NULL,zero_observed BOOLEAN NOT NULL,
      idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,authority_data JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(org_id,project_id,hydration_id),
      UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,hydration_job_id,hydration_job_revision) REFERENCES business_investigation_semantic_hydration_job_revision(org_id,project_id,hydration_job_id,revision),
      CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(status IN('succeeded','partial','blocked','unknown')),
      CHECK(attempted=created_count+updated_count+quarantined_count+unknown_count))""")
    for table in ("business_investigation_semantic_hydration_job_revision","business_investigation_semantic_hydration_receipt"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_biw3_005 ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")
    op.execute("""CREATE FUNCTION semantic_hydration_request_biw3_005(p_job_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_existing record;v_profile record;v_ref jsonb;v_mapping record;v_binding jsonb;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid hydration job';END IF;
        SELECT j.authority_data,j.request_hash INTO v_existing FROM business_investigation_semantic_hydration_job_revision j WHERE j.org_id=v_org AND j.project_id=v_project AND j.idempotency_key=p_idempotency_key;
        IF FOUND THEN IF v_existing.request_hash<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='hydration idempotency conflict';END IF;RETURN QUERY SELECT v_existing.authority_data,true;RETURN;END IF;
        IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project OR p_payload->>'hydrationJobId'<>p_job_id
          OR p_payload->>'schemaVersion'<>'aos.business-investigation.semantic-hydration-job/v1' OR (p_payload->>'revision')::bigint<>1
          OR p_payload->>'requestHash'<>p_request_hash OR p_payload ?| ARRAY['rawPayload','sampleValues','exampleValues','rawRows','pii','secret','token','cookie','password']
          OR jsonb_array_length(p_payload->'ownerCommandBindings')<>jsonb_array_length(p_payload->'mappingRefs')
          OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'ownerCommandBindings') x WHERE x#>>'{ownerCommandRef,resourceType}' NOT IN('OntologyOwnerWriteCommandRevision','DataProductOwnerWriteCommandRevision'))
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='hydration job violates Owner API contract';END IF;
        SELECT p.* INTO v_profile FROM business_investigation_adaptive_profile_revision p WHERE p.org_id=v_org AND p.project_id=v_project
          AND p.profile_id=p_payload#>>'{profileRef,resourceId}' AND p.revision=(p_payload#>>'{profileRef,revision}')::bigint AND p.content_hash=p_payload#>>'{profileRef,contentHash}' FOR SHARE;
        IF v_profile IS NULL OR NOT ((v_profile.authority_data->'unknownFields') @> (p_payload->'unknownFields') AND (p_payload->'unknownFields') @> (v_profile.authority_data->'unknownFields'))
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='hydration requires exact profile and conserved unknowns';END IF;
        FOR v_ref IN SELECT value FROM jsonb_array_elements(p_payload->'mappingRefs') LOOP
          SELECT r.*,h.current_revision,h.current_content_hash INTO v_mapping FROM business_investigation_source_mapping_revision r
            JOIN business_investigation_source_mapping_head h USING(org_id,project_id,mapping_id)
            WHERE r.org_id=v_org AND r.project_id=v_project AND r.mapping_id=v_ref->>'resourceId' AND r.revision=(v_ref->>'revision')::bigint FOR SHARE OF r,h;
          IF NOT FOUND OR v_mapping.status<>'active' OR v_mapping.current_revision<>v_mapping.revision OR v_mapping.content_hash<>v_ref->>'contentHash' OR v_mapping.current_content_hash<>v_ref->>'contentHash'
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='hydration requires current active exact SourceMappingRevision';END IF;
          SELECT value INTO v_binding FROM jsonb_array_elements(p_payload->'ownerCommandBindings') b WHERE b.value->'mappingRef'=v_ref LIMIT 1;
          IF v_binding IS NULL OR v_binding#>>'{canonicalTargetRef,resourceType}'<>v_mapping.canonical_target_type
            OR v_binding#>>'{canonicalTargetRef,resourceId}'<>v_mapping.canonical_target_id
            OR v_binding#>>'{canonicalTargetRef,revision}'<>v_mapping.canonical_target_revision
            OR v_binding#>>'{canonicalTargetRef,contentHash}'<>v_mapping.canonical_target_hash
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='owner command target must exactly match SourceMappingRevision target';END IF;
        END LOOP;
        INSERT INTO business_investigation_semantic_hydration_job_revision(org_id,project_id,hydration_job_id,revision,content_hash,status,profile_id,profile_revision,cutoff_at,idempotency_key,request_hash,authority_data)
        VALUES(v_org,v_project,p_job_id,1,p_payload->>'contentHash',p_payload->>'status',v_profile.profile_id,v_profile.revision,(p_payload->>'cutoffAt')::timestamptz,p_idempotency_key,p_request_hash,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION semantic_hydration_request_biw3_005{REQUEST_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION semantic_hydration_request_biw3_005{REQUEST_SIGNATURE} TO aos_runtime")
    op.execute("""CREATE FUNCTION semantic_hydration_record_biw3_005(p_hydration_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;v_job record;
      BEGIN
        SELECT r.authority_data,r.request_hash INTO v_existing FROM business_investigation_semantic_hydration_receipt r WHERE r.org_id=v_org AND r.project_id=v_project AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN IF v_existing.request_hash<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='hydration receipt idempotency conflict';END IF;RETURN QUERY SELECT v_existing.authority_data,true;RETURN;END IF;
        IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project OR p_payload->>'hydrationId'<>p_hydration_id
          OR p_payload->>'schemaVersion'<>'aos.business-investigation.semantic-hydration-receipt/v1' OR p_payload->>'requestHash'<>p_request_hash
          OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'ownerWriteReceiptRefs') x WHERE x->>'resourceType' NOT IN('OntologyOwnerWriteReceiptRevision','DataProductOwnerWriteReceiptRevision'))
          OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'outputRefs') x WHERE x->>'resourceType' NOT IN('OntologyObjectRevision','OntologyLinkRevision','DataProductRevision'))
          OR (p_payload#>>'{counts,attempted}')::bigint<>(p_payload#>>'{counts,created}')::bigint+(p_payload#>>'{counts,updated}')::bigint+(p_payload#>>'{counts,quarantined}')::bigint+(p_payload#>>'{counts,unknown}')::bigint
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='hydration receipt violates receipt-first contract';END IF;
        SELECT j.* INTO v_job FROM business_investigation_semantic_hydration_job_revision j WHERE j.org_id=v_org AND j.project_id=v_project AND j.hydration_job_id=p_payload#>>'{jobRef,resourceId}' AND j.revision=(p_payload#>>'{jobRef,revision}')::bigint AND j.content_hash=p_payload#>>'{jobRef,contentHash}' FOR SHARE;
        IF v_job IS NULL OR NOT ((v_job.authority_data->'mappingRefs') @> (p_payload->'mappingRefs') AND (p_payload->'mappingRefs') @> (v_job.authority_data->'mappingRefs'))
          OR NOT ((v_job.authority_data->'unknownFields') @> (p_payload->'unknownFields') AND (p_payload->'unknownFields') @> (v_job.authority_data->'unknownFields'))
          OR ((p_payload->>'status')='succeeded' AND (jsonb_array_length(p_payload->'ownerWriteReceiptRefs')=0 OR (jsonb_array_length(p_payload->'outputRefs')=0 AND COALESCE((p_payload->>'zeroObserved')::boolean,false)=false)))
          OR ((p_payload->>'status')<>'succeeded' AND jsonb_array_length(p_payload->'blockers')=0)
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='hydration exact job/output evidence mismatch';END IF;
        INSERT INTO business_investigation_semantic_hydration_receipt(org_id,project_id,hydration_id,hydration_job_id,hydration_job_revision,content_hash,status,attempted,created_count,updated_count,quarantined_count,unknown_count,zero_observed,idempotency_key,request_hash,authority_data)
        VALUES(v_org,v_project,p_hydration_id,v_job.hydration_job_id,v_job.revision,p_payload->>'contentHash',p_payload->>'status',(p_payload#>>'{counts,attempted}')::bigint,(p_payload#>>'{counts,created}')::bigint,(p_payload#>>'{counts,updated}')::bigint,(p_payload#>>'{counts,quarantined}')::bigint,(p_payload#>>'{counts,unknown}')::bigint,(p_payload->>'zeroObserved')::boolean,p_idempotency_key,p_request_hash,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION semantic_hydration_record_biw3_005{RECORD_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION semantic_hydration_record_biw3_005{RECORD_SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM business_investigation_semantic_hydration_job_revision LIMIT 1) OR EXISTS(SELECT 1 FROM business_investigation_semantic_hydration_receipt LIMIT 1) THEN RAISE EXCEPTION 'cannot downgrade biw3_005 with hydration authority' USING ERRCODE='55000';END IF;END $$""")
    op.execute(f"DROP FUNCTION semantic_hydration_record_biw3_005{RECORD_SIGNATURE}")
    op.execute(f"DROP FUNCTION semantic_hydration_request_biw3_005{REQUEST_SIGNATURE}")
    op.execute("DROP TABLE business_investigation_semantic_hydration_receipt")
    op.execute("DROP TABLE business_investigation_semantic_hydration_job_revision")
