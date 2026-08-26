"""Add confirmed SourceField to canonical ontology mapping authority.

Revision ID: biw3_004
Revises: biw3_003
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "biw3_004"
down_revision: str | Sequence[str] | None = "biw3_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLISH_SIGNATURE = "(text,bigint,text,text,jsonb)"
REVIEW_SIGNATURE = "(text,text,text,jsonb)"


def upgrade() -> None:
    op.execute(
        """CREATE TABLE business_investigation_source_mapping_review_decision_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          job_id TEXT NOT NULL, job_revision BIGINT NOT NULL,
          profile_id TEXT NOT NULL, profile_revision BIGINT NOT NULL,
          hypothesis_id TEXT NOT NULL, hypothesis_revision BIGINT NOT NULL,
          source_field TEXT NOT NULL, canonical_target_type TEXT NOT NULL,
          canonical_target_id TEXT NOT NULL, decision TEXT NOT NULL, reviewer TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          authority_data JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id,revision),
          UNIQUE(org_id,project_id,idempotency_key),
          FOREIGN KEY(org_id,project_id,job_id,job_revision)
            REFERENCES business_investigation_schema_profiling_job_revision(org_id,project_id,job_id,revision),
          FOREIGN KEY(org_id,project_id,profile_id,profile_revision)
            REFERENCES business_investigation_adaptive_profile_revision(org_id,project_id,profile_id,revision),
          FOREIGN KEY(org_id,project_id,hypothesis_id,hypothesis_revision)
            REFERENCES business_investigation_semantic_hypothesis_revision(org_id,project_id,hypothesis_id,revision),
          CHECK(revision=1), CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(canonical_target_type IN ('OntologyFieldRevision','OntologyRelationshipRevision')),
          CHECK(decision IN ('confirmed','rejected'))
        )"""
    )
    op.execute(
        """CREATE TABLE business_investigation_source_mapping_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, mapping_id TEXT NOT NULL,
          current_revision BIGINT NOT NULL, current_content_hash TEXT NOT NULL,
          source_field TEXT NOT NULL, canonical_target_type TEXT NOT NULL,
          canonical_target_id TEXT NOT NULL, status TEXT NOT NULL,
          version BIGINT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,mapping_id),
          CHECK(current_revision>=1), CHECK(version>=1),
          CHECK(current_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(canonical_target_type IN ('OntologyFieldRevision','OntologyRelationshipRevision')),
          CHECK(status IN ('active','deprecated'))
        )"""
    )
    op.execute(
        """CREATE TABLE business_investigation_source_mapping_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, mapping_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          prior_revision BIGINT, prior_content_hash TEXT,
          job_id TEXT NOT NULL, job_revision BIGINT NOT NULL, job_content_hash TEXT NOT NULL,
          profile_id TEXT NOT NULL, profile_revision BIGINT NOT NULL, profile_content_hash TEXT NOT NULL,
          hypothesis_id TEXT NOT NULL, hypothesis_revision BIGINT NOT NULL, hypothesis_content_hash TEXT NOT NULL,
          receipt_id TEXT NOT NULL, observation_id TEXT NOT NULL,
          source_field TEXT NOT NULL, canonical_target_type TEXT NOT NULL,
          canonical_target_id TEXT NOT NULL, canonical_target_revision TEXT NOT NULL,
          canonical_target_hash TEXT NOT NULL, status TEXT NOT NULL,
          confirmation_id TEXT NOT NULL, confirmation_revision BIGINT NOT NULL,
          confirmation_hash TEXT NOT NULL, confirmed_by TEXT NOT NULL,
          confirmed_at TIMESTAMPTZ NOT NULL, idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL, authority_data JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,mapping_id,revision),
          UNIQUE(org_id,project_id,idempotency_key),
          FOREIGN KEY(org_id,project_id,job_id,job_revision)
            REFERENCES business_investigation_schema_profiling_job_revision(org_id,project_id,job_id,revision),
          FOREIGN KEY(org_id,project_id,profile_id,profile_revision)
            REFERENCES business_investigation_adaptive_profile_revision(org_id,project_id,profile_id,revision),
          FOREIGN KEY(org_id,project_id,hypothesis_id,hypothesis_revision)
            REFERENCES business_investigation_semantic_hypothesis_revision(org_id,project_id,hypothesis_id,revision),
          FOREIGN KEY(org_id,project_id,confirmation_id,confirmation_revision)
            REFERENCES business_investigation_source_mapping_review_decision_revision(org_id,project_id,decision_id,revision),
          CHECK(revision>=1), CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(job_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(profile_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(hypothesis_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(canonical_target_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(confirmation_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(canonical_target_type IN ('OntologyFieldRevision','OntologyRelationshipRevision')),
          CHECK(status IN ('active','deprecated')),
          CHECK((revision=1 AND prior_revision IS NULL AND prior_content_hash IS NULL)
             OR (revision>1 AND prior_revision=revision-1 AND prior_content_hash ~ '^sha256:[0-9a-f]{64}$'))
        )"""
    )
    op.execute(
        "CREATE INDEX idx_source_mapping_source_biw3_004 ON business_investigation_source_mapping_head(org_id,project_id,source_field,status)"
    )
    op.execute(
        "CREATE INDEX idx_source_mapping_reverse_biw3_004 ON business_investigation_source_mapping_head(org_id,project_id,canonical_target_type,canonical_target_id,status)"
    )
    for table in (
        "business_investigation_source_mapping_review_decision_revision",
        "business_investigation_source_mapping_head",
        "business_investigation_source_mapping_revision",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_biw3_004 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")

    op.execute(
        """CREATE FUNCTION source_mapping_review_record_biw3_004(
          p_decision_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb
        ) RETURNS TABLE(authority_data jsonb,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),'');
          v_existing record; v_job record; v_profile record; v_hypothesis record;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_decision_id)=''
             OR btrim(p_idempotency_key)='' OR p_request_hash !~ '^sha256:[0-9a-f]{64}$'
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid mapping review decision'; END IF;
          SELECT r.authority_data,r.request_hash INTO v_existing
            FROM business_investigation_source_mapping_review_decision_revision r
           WHERE r.org_id=v_org AND r.project_id=v_project AND r.idempotency_key=p_idempotency_key;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash THEN
              RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='mapping review idempotency conflict'; END IF;
            RETURN QUERY SELECT v_existing.authority_data,true; RETURN;
          END IF;
          IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
             OR p_payload->>'decisionId'<>p_decision_id OR (p_payload->>'revision')::bigint<>1
             OR p_payload->>'schemaVersion'<>'aos.business-investigation.source-mapping-review-decision/v1'
             OR p_payload->>'requestHash'<>p_request_hash
             OR p_payload#>>'{jobRef,resourceType}'<>'SchemaProfilingJobRevision'
             OR p_payload#>>'{profileRef,resourceType}'<>'AdaptiveProfileRevision'
             OR p_payload#>>'{hypothesisRef,resourceType}'<>'SemanticHypothesisRevision'
             OR p_payload#>>'{canonicalTargetRef,resourceType}' NOT IN ('OntologyFieldRevision','OntologyRelationshipRevision')
             OR p_payload->>'decision' NOT IN ('confirmed','rejected')
             OR btrim(COALESCE(p_payload->>'reviewer',''))='' OR btrim(COALESCE(p_payload->>'reason',''))=''
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='mapping review violates exact decision contract'; END IF;
          SELECT j.* INTO v_job FROM business_investigation_schema_profiling_job_revision j
           WHERE j.org_id=v_org AND j.project_id=v_project AND j.job_id=p_payload#>>'{jobRef,resourceId}'
             AND j.revision=(p_payload#>>'{jobRef,revision}')::bigint
             AND j.content_hash=p_payload#>>'{jobRef,contentHash}' FOR SHARE;
          SELECT p.* INTO v_profile FROM business_investigation_adaptive_profile_revision p
           WHERE p.org_id=v_org AND p.project_id=v_project AND p.profile_id=p_payload#>>'{profileRef,resourceId}'
             AND p.revision=(p_payload#>>'{profileRef,revision}')::bigint
             AND p.content_hash=p_payload#>>'{profileRef,contentHash}' FOR SHARE;
          SELECT h.* INTO v_hypothesis FROM business_investigation_semantic_hypothesis_revision h
           WHERE h.org_id=v_org AND h.project_id=v_project AND h.hypothesis_id=p_payload#>>'{hypothesisRef,resourceId}'
             AND h.revision=(p_payload#>>'{hypothesisRef,revision}')::bigint
             AND h.content_hash=p_payload#>>'{hypothesisRef,contentHash}' FOR SHARE;
          IF v_job IS NULL OR v_profile IS NULL OR v_hypothesis IS NULL
             OR v_profile.job_id<>v_job.job_id OR v_hypothesis.job_id<>v_job.job_id
             OR v_hypothesis.source_field<>p_payload->>'sourceField'
             OR v_hypothesis.authority_data#>>'{targetRef,resourceType}'<>p_payload#>>'{canonicalTargetRef,resourceType}'
             OR v_hypothesis.authority_data#>>'{targetRef,resourceId}'<>p_payload#>>'{canonicalTargetRef,resourceId}'
             OR v_hypothesis.authority_data#>>'{targetRef,revision}'<>p_payload#>>'{canonicalTargetRef,revision}'
             OR v_hypothesis.authority_data#>>'{targetRef,contentHash}'<>p_payload#>>'{canonicalTargetRef,contentHash}'
             OR v_profile.authority_data->'unknownFields' @> jsonb_build_array(to_jsonb(p_payload->>'sourceField'))
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='mapping review exact profiling evidence mismatch'; END IF;
          INSERT INTO business_investigation_source_mapping_review_decision_revision(
            org_id,project_id,decision_id,revision,content_hash,job_id,job_revision,
            profile_id,profile_revision,hypothesis_id,hypothesis_revision,source_field,
            canonical_target_type,canonical_target_id,decision,reviewer,idempotency_key,request_hash,authority_data)
          VALUES(v_org,v_project,p_decision_id,1,p_payload->>'contentHash',v_job.job_id,v_job.revision,
            v_profile.profile_id,v_profile.revision,v_hypothesis.hypothesis_id,v_hypothesis.revision,
            p_payload->>'sourceField',p_payload#>>'{canonicalTargetRef,resourceType}',
            p_payload#>>'{canonicalTargetRef,resourceId}',p_payload->>'decision',p_payload->>'reviewer',
            p_idempotency_key,p_request_hash,p_payload);
          RETURN QUERY SELECT p_payload,false;
        END $$"""
    )
    op.execute(f"REVOKE ALL ON FUNCTION source_mapping_review_record_biw3_004{REVIEW_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION source_mapping_review_record_biw3_004{REVIEW_SIGNATURE} TO aos_runtime")

    op.execute(
        """CREATE FUNCTION source_mapping_publish_biw3_004(
          p_mapping_id text,p_expected_version bigint,p_idempotency_key text,
          p_request_hash text,p_payload jsonb
        ) RETURNS TABLE(authority_data jsonb,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),'');
          v_existing record; v_head record; v_job record; v_profile record; v_hypothesis record; v_review record;
          v_revision bigint:=(p_payload->>'revision')::bigint;
          v_source text:=p_payload->>'sourceField';
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_mapping_id)=''
             OR p_expected_version<0 OR btrim(p_idempotency_key)=''
             OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR p_payload IS NULL
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid tenant-bound source mapping'; END IF;
          SELECT r.authority_data,r.request_hash INTO v_existing
            FROM business_investigation_source_mapping_revision r
           WHERE r.org_id=v_org AND r.project_id=v_project AND r.idempotency_key=p_idempotency_key;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash THEN
              RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='source mapping idempotency conflict'; END IF;
            RETURN QUERY SELECT v_existing.authority_data,true; RETURN;
          END IF;
          IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
             OR p_payload->>'mappingId'<>p_mapping_id
             OR p_payload->>'schemaVersion'<>'aos.business-investigation.source-mapping-revision/v1'
             OR p_payload->>'requestHash'<>p_request_hash
             OR p_payload->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
             OR p_payload#>>'{jobRef,resourceType}'<>'SchemaProfilingJobRevision'
             OR p_payload#>>'{profileRef,resourceType}'<>'AdaptiveProfileRevision'
             OR p_payload#>>'{hypothesisRef,resourceType}'<>'SemanticHypothesisRevision'
             OR p_payload#>>'{receiptRef,resourceType}'<>'ObservationReceipt'
             OR p_payload#>>'{observationRef,resourceType}'<>'PlatformObservation'
             OR p_payload#>>'{confirmationRef,resourceType}'<>'HumanReviewDecisionRevision'
             OR p_payload#>>'{canonicalTargetRef,resourceType}' NOT IN ('OntologyFieldRevision','OntologyRelationshipRevision')
             OR btrim(COALESCE(p_payload->>'confirmedBy',''))='' OR btrim(COALESCE(p_payload->>'reason',''))=''
             OR p_payload ?| ARRAY['rawPayload','sampleValues','exampleValues','rawRows','observedValues','pii','secret','token','cookie','password']
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='source mapping violates confirmed exact-ref contract'; END IF;
          SELECT h.* INTO v_head FROM business_investigation_source_mapping_head h
           WHERE h.org_id=v_org AND h.project_id=v_project AND h.mapping_id=p_mapping_id FOR UPDATE;
          IF FOUND THEN
            IF v_head.version<>p_expected_version OR v_revision<>v_head.current_revision+1
               OR p_payload#>>'{priorRef,resourceType}'<>'SourceMappingRevision'
               OR p_payload#>>'{priorRef,resourceId}'<>p_mapping_id
               OR (p_payload#>>'{priorRef,revision}')::bigint<>v_head.current_revision
               OR p_payload#>>'{priorRef,contentHash}'<>v_head.current_content_hash
            THEN RAISE EXCEPTION USING ERRCODE='BO002',MESSAGE='source mapping CAS or priorRef conflict'; END IF;
          ELSIF p_expected_version<>0 OR v_revision<>1 OR p_payload->'priorRef' IS DISTINCT FROM 'null'::jsonb THEN
            RAISE EXCEPTION USING ERRCODE='BO002',MESSAGE='new source mapping requires expectedVersion 0 and revision 1';
          END IF;
          SELECT j.* INTO v_job FROM business_investigation_schema_profiling_job_revision j
           WHERE j.org_id=v_org AND j.project_id=v_project
             AND j.job_id=p_payload#>>'{jobRef,resourceId}'
             AND j.revision=(p_payload#>>'{jobRef,revision}')::bigint
             AND j.content_hash=p_payload#>>'{jobRef,contentHash}' FOR SHARE;
          SELECT p.* INTO v_profile FROM business_investigation_adaptive_profile_revision p
           WHERE p.org_id=v_org AND p.project_id=v_project
             AND p.profile_id=p_payload#>>'{profileRef,resourceId}'
             AND p.revision=(p_payload#>>'{profileRef,revision}')::bigint
             AND p.content_hash=p_payload#>>'{profileRef,contentHash}' FOR SHARE;
          SELECT h.* INTO v_hypothesis FROM business_investigation_semantic_hypothesis_revision h
           WHERE h.org_id=v_org AND h.project_id=v_project
             AND h.hypothesis_id=p_payload#>>'{hypothesisRef,resourceId}'
             AND h.revision=(p_payload#>>'{hypothesisRef,revision}')::bigint
             AND h.content_hash=p_payload#>>'{hypothesisRef,contentHash}' FOR SHARE;
          SELECT r.* INTO v_review FROM business_investigation_source_mapping_review_decision_revision r
           WHERE r.org_id=v_org AND r.project_id=v_project
             AND r.decision_id=p_payload#>>'{confirmationRef,resourceId}'
             AND r.revision=(p_payload#>>'{confirmationRef,revision}')::bigint
             AND r.content_hash=p_payload#>>'{confirmationRef,contentHash}' FOR SHARE;
          IF v_job IS NULL OR v_profile IS NULL OR v_hypothesis IS NULL OR v_review IS NULL
             OR v_profile.job_id<>v_job.job_id OR v_hypothesis.job_id<>v_job.job_id
             OR v_hypothesis.source_field<>v_source
             OR v_review.decision<>'confirmed' OR v_review.reviewer<>p_payload->>'confirmedBy'
             OR v_review.job_id<>v_job.job_id OR v_review.profile_id<>v_profile.profile_id
             OR v_review.hypothesis_id<>v_hypothesis.hypothesis_id OR v_review.source_field<>v_source
             OR v_review.canonical_target_type<>p_payload#>>'{canonicalTargetRef,resourceType}'
             OR v_review.canonical_target_id<>p_payload#>>'{canonicalTargetRef,resourceId}'
             OR v_hypothesis.authority_data#>>'{targetRef,resourceType}'<>p_payload#>>'{canonicalTargetRef,resourceType}'
             OR v_hypothesis.authority_data#>>'{targetRef,resourceId}'<>p_payload#>>'{canonicalTargetRef,resourceId}'
             OR v_hypothesis.authority_data#>>'{targetRef,revision}'<>p_payload#>>'{canonicalTargetRef,revision}'
             OR v_hypothesis.authority_data#>>'{targetRef,contentHash}'<>p_payload#>>'{canonicalTargetRef,contentHash}'
             OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(v_profile.authority_data->'hypothesisRefs') x
                WHERE x->>'resourceType'=p_payload#>>'{hypothesisRef,resourceType}'
                  AND x->>'resourceId'=p_payload#>>'{hypothesisRef,resourceId}'
                  AND x->>'revision'=p_payload#>>'{hypothesisRef,revision}'
                  AND x->>'contentHash'=p_payload#>>'{hypothesisRef,contentHash}')
             OR v_profile.authority_data->'unknownFields' @> jsonb_build_array(to_jsonb(v_source))
             OR NOT (v_profile.authority_data->'coveredFields' @> jsonb_build_array(to_jsonb(v_source)))
             OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(v_job.authority_data->'receiptRefs') x
                WHERE x->>'resourceId'=p_payload#>>'{receiptRef,resourceId}'
                  AND x->>'revision'=p_payload#>>'{receiptRef,revision}'
                  AND x->>'contentHash'=p_payload#>>'{receiptRef,contentHash}')
             OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(v_job.authority_data->'observationRefs') x
                WHERE x->>'resourceId'=p_payload#>>'{observationRef,resourceId}'
                  AND x->>'revision'=p_payload#>>'{observationRef,revision}'
                  AND x->>'contentHash'=p_payload#>>'{observationRef,contentHash}')
             OR NOT EXISTS(SELECT 1 FROM business_investigation_observation_receipt r
                WHERE r.org_id=v_org AND r.project_id=v_project
                  AND r.receipt_id=p_payload#>>'{receiptRef,resourceId}'
                  AND r.content_hash=p_payload#>>'{receiptRef,contentHash}')
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='source mapping exact profiling evidence mismatch or unknown field'; END IF;
          INSERT INTO business_investigation_source_mapping_revision(
            org_id,project_id,mapping_id,revision,content_hash,prior_revision,prior_content_hash,
            job_id,job_revision,job_content_hash,profile_id,profile_revision,profile_content_hash,
            hypothesis_id,hypothesis_revision,hypothesis_content_hash,receipt_id,observation_id,
            source_field,canonical_target_type,canonical_target_id,canonical_target_revision,
            canonical_target_hash,status,confirmation_id,confirmation_revision,confirmation_hash,
            confirmed_by,confirmed_at,idempotency_key,request_hash,authority_data)
          VALUES(v_org,v_project,p_mapping_id,v_revision,p_payload->>'contentHash',
            CASE WHEN v_revision=1 THEN NULL ELSE (p_payload#>>'{priorRef,revision}')::bigint END,
            CASE WHEN v_revision=1 THEN NULL ELSE p_payload#>>'{priorRef,contentHash}' END,
            v_job.job_id,v_job.revision,v_job.content_hash,v_profile.profile_id,v_profile.revision,v_profile.content_hash,
            v_hypothesis.hypothesis_id,v_hypothesis.revision,v_hypothesis.content_hash,
            p_payload#>>'{receiptRef,resourceId}',p_payload#>>'{observationRef,resourceId}',v_source,
            p_payload#>>'{canonicalTargetRef,resourceType}',p_payload#>>'{canonicalTargetRef,resourceId}',
            p_payload#>>'{canonicalTargetRef,revision}',p_payload#>>'{canonicalTargetRef,contentHash}',
            p_payload->>'status',p_payload#>>'{confirmationRef,resourceId}',
            (p_payload#>>'{confirmationRef,revision}')::bigint,p_payload#>>'{confirmationRef,contentHash}',
            p_payload->>'confirmedBy',(p_payload->>'confirmedAt')::timestamptz,
            p_idempotency_key,p_request_hash,p_payload);
          INSERT INTO business_investigation_source_mapping_head(
            org_id,project_id,mapping_id,current_revision,current_content_hash,source_field,
            canonical_target_type,canonical_target_id,status,version)
          VALUES(v_org,v_project,p_mapping_id,v_revision,p_payload->>'contentHash',v_source,
            p_payload#>>'{canonicalTargetRef,resourceType}',p_payload#>>'{canonicalTargetRef,resourceId}',
            p_payload->>'status',p_expected_version+1)
          ON CONFLICT(org_id,project_id,mapping_id) DO UPDATE SET
            current_revision=EXCLUDED.current_revision,current_content_hash=EXCLUDED.current_content_hash,
            source_field=EXCLUDED.source_field,canonical_target_type=EXCLUDED.canonical_target_type,
            canonical_target_id=EXCLUDED.canonical_target_id,status=EXCLUDED.status,
            version=EXCLUDED.version,updated_at=NOW();
          RETURN QUERY SELECT p_payload,false;
        END $$"""
    )
    op.execute(f"REVOKE ALL ON FUNCTION source_mapping_publish_biw3_004{PUBLISH_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION source_mapping_publish_biw3_004{PUBLISH_SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM business_investigation_source_mapping_revision LIMIT 1)
          THEN RAISE EXCEPTION 'cannot downgrade biw3_004 with source mappings' USING ERRCODE='55000'; END IF;
        END $$"""
    )
    op.execute(f"DROP FUNCTION source_mapping_publish_biw3_004{PUBLISH_SIGNATURE}")
    op.execute(f"DROP FUNCTION source_mapping_review_record_biw3_004{REVIEW_SIGNATURE}")
    op.execute("DROP TABLE business_investigation_source_mapping_revision")
    op.execute("DROP TABLE business_investigation_source_mapping_head")
    op.execute("DROP TABLE business_investigation_source_mapping_review_decision_revision")
