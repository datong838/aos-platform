"""Add governed aggregate schema profiling authority.

Revision ID: biw3_003
Revises: biw3_002
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "biw3_003"
down_revision: str | Sequence[str] | None = "biw3_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_SIGNATURE = "(text,text,text,jsonb)"
RESULT_SIGNATURE = "(text,text,text,jsonb,jsonb)"


def upgrade() -> None:
    op.execute(
        """CREATE TABLE business_investigation_schema_profiling_job_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, job_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          status TEXT NOT NULL, cutoff_at TIMESTAMPTZ NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          authority_data JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,job_id,revision),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(revision=1), CHECK(status IN ('requested','blocked','unknown')),
          CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$')
        )"""
    )
    op.execute(
        """CREATE TABLE business_investigation_semantic_hypothesis_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, hypothesis_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          job_id TEXT NOT NULL, job_revision BIGINT NOT NULL,
          source_field TEXT NOT NULL, target_resource_type TEXT NOT NULL,
          risk_category TEXT NOT NULL, requires_human_review BOOLEAN NOT NULL,
          authority_data JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,hypothesis_id,revision),
          UNIQUE(org_id,project_id,job_id,job_revision,source_field),
          FOREIGN KEY(org_id,project_id,job_id,job_revision)
            REFERENCES business_investigation_schema_profiling_job_revision(org_id,project_id,job_id,revision),
          CHECK(revision=1),
          CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(target_resource_type IN ('OntologyFieldRevision','OntologyRelationshipRevision')),
          CHECK(risk_category IN ('ordinary','identity','customer_ownership','commission','health','pii')),
          CHECK(risk_category='ordinary' OR requires_human_review)
        )"""
    )
    op.execute(
        """CREATE TABLE business_investigation_adaptive_profile_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, profile_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          job_id TEXT NOT NULL, job_revision BIGINT NOT NULL,
          status TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          authority_data JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,profile_id,revision),
          UNIQUE(org_id,project_id,idempotency_key),
          FOREIGN KEY(org_id,project_id,job_id,job_revision)
            REFERENCES business_investigation_schema_profiling_job_revision(org_id,project_id,job_id,revision),
          CHECK(revision=1), CHECK(status IN ('completed','blocked','unknown')),
          CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$')
        )"""
    )
    for table in (
        "business_investigation_schema_profiling_job_revision",
        "business_investigation_semantic_hypothesis_revision",
        "business_investigation_adaptive_profile_revision",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_biw3_003 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")

    op.execute(
        """CREATE FUNCTION schema_profiling_job_record_biw3_003(
          p_job_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb
        ) RETURNS TABLE(authority_data jsonb,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_existing record;
          v_receipt jsonb; v_field jsonb; v_receipt_row record;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_job_id)='' OR btrim(p_idempotency_key)=''
             OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR p_payload IS NULL
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid tenant-bound profiling job'; END IF;
          SELECT j.authority_data,j.request_hash INTO v_existing
            FROM business_investigation_schema_profiling_job_revision j
           WHERE j.org_id=v_org AND j.project_id=v_project AND j.idempotency_key=p_idempotency_key;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash THEN
              RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='profiling job idempotency conflict'; END IF;
            RETURN QUERY SELECT v_existing.authority_data,true; RETURN;
          END IF;
          IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
             OR p_payload->>'jobId'<>p_job_id OR (p_payload->>'revision')::bigint<>1
             OR p_payload->>'schemaVersion'<>'aos.business-investigation.schema-profiling-job/v1'
             OR p_payload->>'requestHash'<>p_request_hash
             OR p_payload->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
             OR p_payload#>>'{ontologyRequirementRef,resourceType}'<>'OntologyRequirementRevision'
             OR jsonb_array_length(p_payload->'fieldSummaries')<1
             OR jsonb_array_length(p_payload->'fieldSummaries')>(p_payload->>'maxFields')::integer
             OR p_payload ?| ARRAY['rawPayload','sampleValues','exampleValues','rawRows','pii','secret','token','cookie','password']
             OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'fieldSummaries') f
                 WHERE f ?| ARRAY['rawPayload','sampleValues','exampleValues','rawRows','observedValues']
                    OR (f->>'rowCount')::bigint<>(f->>'nonNullCount')::bigint+(f->>'nullCount')::bigint
                    OR (f->>'duplicateCount')::bigint<>(f->>'nonNullCount')::bigint-(f->>'distinctCount')::bigint
                    OR f#>>'{receiptRef,resourceType}'<>'ObservationReceipt'
                    OR f#>>'{observationRef,resourceType}'<>'PlatformObservation')
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='profiling job violates aggregate-only contract'; END IF;
          FOR v_receipt IN SELECT value FROM jsonb_array_elements(p_payload->'receiptRefs') LOOP
            IF v_receipt->>'resourceType'<>'ObservationReceipt' THEN
              RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='profiling requires ObservationReceipt refs'; END IF;
            SELECT r.* INTO v_receipt_row FROM business_investigation_observation_receipt r
             WHERE r.org_id=v_org AND r.project_id=v_project
               AND r.receipt_id=v_receipt->>'resourceId'
               AND r.content_hash=v_receipt->>'contentHash' FOR SHARE;
            IF NOT FOUND OR (v_receipt->>'revision')::bigint<>1 THEN
              RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='profiling requires exact ObservationReceipt authority'; END IF;
          END LOOP;
          FOR v_field IN SELECT value FROM jsonb_array_elements(p_payload->'fieldSummaries') LOOP
            IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'receiptRefs') r
              WHERE r=v_field->'receiptRef') OR NOT EXISTS(
                SELECT 1 FROM jsonb_array_elements(p_payload->'observationRefs') o
                 WHERE o=v_field->'observationRef')
            THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='field summaries require declared exact evidence'; END IF;
          END LOOP;
          INSERT INTO business_investigation_schema_profiling_job_revision(
            org_id,project_id,job_id,revision,content_hash,status,cutoff_at,idempotency_key,
            request_hash,authority_data)
          VALUES(v_org,v_project,p_job_id,1,p_payload->>'contentHash',p_payload->>'status',
            (p_payload->>'cutoffAt')::timestamptz,p_idempotency_key,p_request_hash,p_payload);
          RETURN QUERY SELECT p_payload,false;
        END $$"""
    )
    op.execute(f"REVOKE ALL ON FUNCTION schema_profiling_job_record_biw3_003{JOB_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION schema_profiling_job_record_biw3_003{JOB_SIGNATURE} TO aos_runtime")

    op.execute(
        """CREATE FUNCTION schema_profiling_result_record_biw3_003(
          p_profile_id text,p_idempotency_key text,p_request_hash text,
          p_hypotheses jsonb,p_profile jsonb
        ) RETURNS TABLE(authority_data jsonb,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_existing record;
          v_job record; v_h jsonb; v_ref jsonb;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_profile_id)='' OR btrim(p_idempotency_key)=''
             OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR jsonb_typeof(p_hypotheses)<>'array'
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid tenant-bound profiling result'; END IF;
          SELECT p.authority_data,p.request_hash INTO v_existing
            FROM business_investigation_adaptive_profile_revision p
           WHERE p.org_id=v_org AND p.project_id=v_project AND p.idempotency_key=p_idempotency_key;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash THEN
              RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='profiling result idempotency conflict'; END IF;
            RETURN QUERY SELECT v_existing.authority_data,true; RETURN;
          END IF;
          IF p_profile#>>'{tenant,orgId}'<>v_org OR p_profile#>>'{tenant,projectId}'<>v_project
             OR p_profile->>'profileId'<>p_profile_id OR (p_profile->>'revision')::bigint<>1
             OR p_profile->>'schemaVersion'<>'aos.business-investigation.adaptive-profile-revision/v1'
             OR p_profile->>'requestHash'<>p_request_hash
             OR p_profile#>>'{jobRef,resourceType}'<>'SchemaProfilingJobRevision'
             OR (p_profile#>>'{coverage,required}')::integer<>jsonb_array_length(p_profile->'requiredFields')
             OR (p_profile#>>'{coverage,fulfilled}')::integer<>jsonb_array_length(p_profile->'coveredFields')
             OR (p_profile#>>'{coverage,unknown}')::integer<>jsonb_array_length(p_profile->'unknownFields')
             OR (p_profile#>>'{coverage,required}')::integer<>(p_profile#>>'{coverage,fulfilled}')::integer+
                 (p_profile#>>'{coverage,unknown}')::integer
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='adaptive profile violates coverage conservation'; END IF;
          SELECT j.* INTO v_job FROM business_investigation_schema_profiling_job_revision j
           WHERE j.org_id=v_org AND j.project_id=v_project
             AND j.job_id=p_profile#>>'{jobRef,resourceId}'
             AND j.revision=(p_profile#>>'{jobRef,revision}')::bigint
             AND j.content_hash=p_profile#>>'{jobRef,contentHash}' FOR SHARE;
          IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='profile requires exact profiling job'; END IF;
          FOR v_h IN SELECT value FROM jsonb_array_elements(p_hypotheses) LOOP
            IF v_h#>>'{tenant,orgId}'<>v_org OR v_h#>>'{tenant,projectId}'<>v_project
               OR v_h->>'schemaVersion'<>'aos.business-investigation.semantic-hypothesis/v1'
               OR v_h#>>'{jobRef,resourceId}'<>v_job.job_id
               OR v_h#>>'{jobRef,contentHash}'<>v_job.content_hash
               OR v_h#>>'{targetRef,resourceType}' NOT IN ('OntologyFieldRevision','OntologyRelationshipRevision')
               OR (v_h->>'riskCategory' IN ('identity','customer_ownership','commission','health','pii')
                   AND COALESCE((v_h->>'requiresHumanReview')::boolean,false)=false)
               OR EXISTS(SELECT 1 FROM jsonb_array_elements(v_h->'evidenceRefs') e
                    WHERE e->>'resourceType' NOT IN ('ObservationReceipt','PlatformObservation'))
            THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='semantic hypothesis violates governed suggestion contract'; END IF;
            INSERT INTO business_investigation_semantic_hypothesis_revision(
              org_id,project_id,hypothesis_id,revision,content_hash,job_id,job_revision,
              source_field,target_resource_type,risk_category,requires_human_review,authority_data)
            VALUES(v_org,v_project,v_h->>'hypothesisId',1,v_h->>'contentHash',v_job.job_id,v_job.revision,
              v_h->>'sourceField',v_h#>>'{targetRef,resourceType}',v_h->>'riskCategory',
              (v_h->>'requiresHumanReview')::boolean,v_h);
          END LOOP;
          FOR v_ref IN SELECT value FROM jsonb_array_elements(p_profile->'hypothesisRefs') LOOP
            IF NOT EXISTS(SELECT 1 FROM business_investigation_semantic_hypothesis_revision h
              WHERE h.org_id=v_org AND h.project_id=v_project AND h.hypothesis_id=v_ref->>'resourceId'
                AND h.revision=(v_ref->>'revision')::bigint AND h.content_hash=v_ref->>'contentHash'
                AND h.job_id=v_job.job_id)
            THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='profile hypothesisRefs are not exact'; END IF;
          END LOOP;
          INSERT INTO business_investigation_adaptive_profile_revision(
            org_id,project_id,profile_id,revision,content_hash,job_id,job_revision,status,
            idempotency_key,request_hash,authority_data)
          VALUES(v_org,v_project,p_profile_id,1,p_profile->>'contentHash',v_job.job_id,v_job.revision,
            p_profile->>'status',p_idempotency_key,p_request_hash,p_profile);
          RETURN QUERY SELECT p_profile,false;
        END $$"""
    )
    op.execute(f"REVOKE ALL ON FUNCTION schema_profiling_result_record_biw3_003{RESULT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION schema_profiling_result_record_biw3_003{RESULT_SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM business_investigation_schema_profiling_job_revision LIMIT 1)
             OR EXISTS(SELECT 1 FROM business_investigation_semantic_hypothesis_revision LIMIT 1)
             OR EXISTS(SELECT 1 FROM business_investigation_adaptive_profile_revision LIMIT 1)
          THEN RAISE EXCEPTION 'cannot downgrade biw3_003 with profiling authority' USING ERRCODE='55000'; END IF;
        END $$"""
    )
    op.execute(f"DROP FUNCTION schema_profiling_result_record_biw3_003{RESULT_SIGNATURE}")
    op.execute(f"DROP FUNCTION schema_profiling_job_record_biw3_003{JOB_SIGNATURE}")
    op.execute("DROP TABLE business_investigation_adaptive_profile_revision")
    op.execute("DROP TABLE business_investigation_semantic_hypothesis_revision")
    op.execute("DROP TABLE business_investigation_schema_profiling_job_revision")
