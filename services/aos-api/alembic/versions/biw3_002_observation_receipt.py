"""Add append-only exact ObservationReceipt authority.

Revision ID: biw3_002
Revises: biw3_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "biw3_002"
down_revision: str | Sequence[str] | None = "biw3_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECORD_SIGNATURE = "(text,text,text,jsonb)"


def upgrade() -> None:
    op.execute(
        """CREATE TABLE business_investigation_observation_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          plan_id TEXT NOT NULL, plan_revision BIGINT NOT NULL, plan_content_hash TEXT NOT NULL,
          step_id TEXT NOT NULL, capability_id TEXT NOT NULL,
          lease_id TEXT NOT NULL, lease_revision INTEGER NOT NULL, lease_content_hash TEXT NOT NULL,
          requirement_id TEXT NOT NULL, requirement_revision BIGINT NOT NULL,
          requirement_content_hash TEXT NOT NULL,
          status TEXT NOT NULL, semantic_route TEXT NOT NULL,
          cutoff_at TIMESTAMPTZ NOT NULL, content_hash TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          authority_data JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,receipt_id),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(status IN ('succeeded','partial','blocked','unknown')),
          CHECK(plan_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(lease_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(requirement_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(left(semantic_route,1)='/' AND semantic_route NOT LIKE '%?%'
            AND semantic_route NOT LIKE '%#%' AND semantic_route NOT LIKE '%..%'),
          FOREIGN KEY(org_id,project_id,plan_id,plan_revision)
            REFERENCES business_investigation_observation_plan_revision(org_id,project_id,plan_id,revision),
          FOREIGN KEY(org_id,project_id,lease_id)
            REFERENCES business_investigation_observation_session_lease(org_id,project_id,lease_id),
          FOREIGN KEY(org_id,project_id,requirement_id,requirement_revision)
            REFERENCES data_requirement_revision(org_id,project_id,requirement_id,revision)
        )"""
    )
    op.execute(
        "CREATE INDEX idx_observation_receipt_plan_step_biw3_002 ON business_investigation_observation_receipt(org_id,project_id,plan_id,plan_revision,step_id,created_at)"
    )
    op.execute("ALTER TABLE business_investigation_observation_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE business_investigation_observation_receipt FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_business_investigation_observation_receipt_biw3_002
        ON business_investigation_observation_receipt TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute("GRANT SELECT ON business_investigation_observation_receipt TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON business_investigation_observation_receipt FROM aos_runtime")

    op.execute(
        """CREATE FUNCTION observation_receipt_record_biw3_002(
          p_receipt_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb
        ) RETURNS TABLE(authority_data jsonb,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_existing record;
          v_plan_ref jsonb:=p_payload->'planRef'; v_step_ref jsonb:=p_payload->'stepRef';
          v_lease_ref jsonb:=p_payload->'sessionRef'; v_requirement jsonb:=p_payload->'requirementRef';
          v_plan record; v_lease record; v_step_id text; v_step jsonb;
          v_started timestamptz; v_cutoff timestamptz; v_finished timestamptz;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_receipt_id)='' OR btrim(p_idempotency_key)=''
             OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR p_payload IS NULL
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid tenant-bound observation receipt'; END IF;
          SELECT r.authority_data,r.request_hash INTO v_existing
            FROM business_investigation_observation_receipt r
           WHERE r.org_id=v_org AND r.project_id=v_project AND r.idempotency_key=p_idempotency_key;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash THEN
              RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='observation receipt idempotency conflict'; END IF;
            RETURN QUERY SELECT v_existing.authority_data,true; RETURN;
          END IF;
          IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
             OR NOT (p_payload ?& ARRAY['receiptId','planRef','stepRef','capabilityRef','sessionRef','requirementRef',
                 'status','semanticRoute','startedAt','cutoffAt','finishedAt','coverage','locationEvidenceRefs',
                 'factObservationRefs','pageFingerprint','nonClaims','blockers','contentHash','requestHash'])
             OR p_payload->>'receiptId'<>p_receipt_id
             OR p_payload->>'schemaVersion'<>'aos.business-investigation.observation-receipt/v1'
             OR p_payload->>'requestHash'<>p_request_hash
             OR v_plan_ref->>'resourceType'<>'ObservationPlanRevision'
             OR v_step_ref->>'resourceType'<>'ObservationPlanStepRevision'
             OR p_payload#>>'{capabilityRef,resourceType}'<>'CapabilityRevision'
             OR v_lease_ref->>'resourceType'<>'ObservationSessionLeaseRevision'
             OR v_requirement->>'resourceType'<>'DataRequirementRevision'
             OR left(p_payload->>'semanticRoute',1)<>'/' OR p_payload->>'semanticRoute' LIKE '%?%'
             OR p_payload->>'semanticRoute' LIKE '%#%' OR p_payload->>'semanticRoute' LIKE '%..%'
             OR p_payload->>'pageFingerprint' !~ '^sha256:[0-9a-f]{64}$'
             OR p_payload->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
             OR p_payload ?| ARRAY['rawUrl','url','query','html','dom','screenshot','observedValues','rawPayload',
                                  'cookie','password','captcha','token','localStorage','sessionPayload']
             OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'locationEvidenceRefs') e
                 WHERE e->>'resourceType' NOT IN ('PageScreenshotArtifactRevision','DOMSnapshotArtifactRevision','ReadOnlyExportArtifactRevision')
                    OR e->>'contentHash' !~ '^sha256:[0-9a-f]{64}$' OR (e->>'revision')::integer<1)
             OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'factObservationRefs') f
                 WHERE f->>'resourceType'<>'PlatformObservation'
                    OR f->>'contentHash' !~ '^sha256:[0-9a-f]{64}$' OR (f->>'revision')::integer<1)
             OR (jsonb_array_length(p_payload->'factObservationRefs')>0
                 AND jsonb_array_length(p_payload->'observedFieldSet')=0)
             OR jsonb_array_length(p_payload->'nonClaims')=0
             OR ((p_payload->>'status')='succeeded' AND
                 (jsonb_array_length(p_payload->'blockers')>0 OR
                  jsonb_array_length(p_payload->'locationEvidenceRefs')+jsonb_array_length(p_payload->'factObservationRefs')=0))
             OR ((p_payload->>'status')<>'succeeded' AND jsonb_array_length(p_payload->'blockers')=0)
             OR (p_payload#>>'{coverage,pagesObserved}')::integer>(p_payload#>>'{coverage,pagesExpected}')::integer
             OR (p_payload#>>'{coverage,rowsObserved}')::integer+(p_payload#>>'{coverage,rowsUnknown}')::integer
                  >(p_payload#>>'{coverage,rowsExpected}')::integer
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='observation receipt violates evidence/fact contract'; END IF;
          v_started:=(p_payload->>'startedAt')::timestamptz;
          v_cutoff:=(p_payload->>'cutoffAt')::timestamptz;
          v_finished:=(p_payload->>'finishedAt')::timestamptz;
          IF v_started>v_cutoff OR v_cutoff>v_finished
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='observation receipt timestamp order is invalid'; END IF;
          SELECT r.*,h.current_revision,h.current_content_hash INTO v_plan
            FROM business_investigation_observation_plan_revision r
            JOIN business_investigation_observation_plan_head h USING(org_id,project_id,plan_id)
           WHERE r.org_id=v_org AND r.project_id=v_project AND r.plan_id=v_plan_ref->>'resourceId'
             AND r.revision=(v_plan_ref->>'revision')::bigint FOR SHARE OF r,h;
          IF NOT FOUND OR v_plan.current_revision<>v_plan.revision
             OR v_plan.current_content_hash<>v_plan_ref->>'contentHash'
             OR v_plan.content_hash<>v_plan_ref->>'contentHash'
             OR v_step_ref->>'revision'<>v_plan_ref->>'revision'
             OR v_step_ref->>'contentHash'<>v_plan_ref->>'contentHash'
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='receipt requires current exact observation plan'; END IF;
          IF left(v_step_ref->>'resourceId',length(v_plan.plan_id)+1)<>v_plan.plan_id||':'
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='receipt step identity is outside exact plan'; END IF;
          v_step_id:=substring(v_step_ref->>'resourceId' FROM length(v_plan.plan_id)+2);
          SELECT s INTO v_step FROM jsonb_array_elements(v_plan.authority_data->'steps') s WHERE s->>'stepId'=v_step_id;
          IF NOT FOUND OR v_step_id='' OR p_payload->>'semanticRoute'<>v_step->>'routePattern'
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='receipt step is not in exact observation plan'; END IF;
          SELECT * INTO v_lease FROM business_investigation_observation_session_lease l
           WHERE l.org_id=v_org AND l.project_id=v_project AND l.lease_id=v_lease_ref->>'resourceId' FOR SHARE;
          IF NOT FOUND OR v_lease.status<>'active' OR v_lease.expires_at<=NOW()
             OR v_lease.revision<>(v_lease_ref->>'revision')::integer
             OR v_lease.content_hash<>v_lease_ref->>'contentHash'
             OR v_plan.lease_id<>v_lease.lease_id OR v_plan.lease_revision<>v_lease.revision
             OR v_plan.lease_content_hash<>v_lease.content_hash
             OR v_plan.requirement_id<>v_requirement->>'resourceId'
             OR v_plan.requirement_revision<>(v_requirement->>'revision')::bigint
             OR v_plan.requirement_content_hash<>v_requirement->>'contentHash'
             OR (EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'locationEvidenceRefs') e
                         WHERE e->>'resourceType'='ReadOnlyExportArtifactRevision')
                 AND (v_lease.authority_data->'exportAuthorizationRef' IS NULL
                      OR v_lease.authority_data->'exportAuthorizationRef'='null'::jsonb))
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='receipt requires current active exact session lease'; END IF;
          IF NOT EXISTS(SELECT 1 FROM data_requirement_head h WHERE h.org_id=v_org AND h.project_id=v_project
             AND h.requirement_id=v_requirement->>'resourceId'
             AND h.current_revision=(v_requirement->>'revision')::bigint
             AND ('sha256:'||h.current_content_hash)=v_requirement->>'contentHash')
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='receipt requires current DataRequirement exact ref'; END IF;
          INSERT INTO business_investigation_observation_receipt(
            org_id,project_id,receipt_id,plan_id,plan_revision,plan_content_hash,step_id,capability_id,
            lease_id,lease_revision,lease_content_hash,requirement_id,requirement_revision,requirement_content_hash,
            status,semantic_route,cutoff_at,content_hash,idempotency_key,request_hash,authority_data)
          VALUES(v_org,v_project,p_receipt_id,v_plan.plan_id,v_plan.revision,v_plan.content_hash,v_step_id,
            p_payload#>>'{capabilityRef,resourceId}',v_lease.lease_id,v_lease.revision,v_lease.content_hash,
            v_plan.requirement_id,v_plan.requirement_revision,v_plan.requirement_content_hash,p_payload->>'status',
            p_payload->>'semanticRoute',v_cutoff,p_payload->>'contentHash',
            p_idempotency_key,p_request_hash,p_payload);
          RETURN QUERY SELECT p_payload,false;
        END $$"""
    )
    op.execute(f"REVOKE ALL ON FUNCTION observation_receipt_record_biw3_002{RECORD_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION observation_receipt_record_biw3_002{RECORD_SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM business_investigation_observation_receipt LIMIT 1)
          THEN RAISE EXCEPTION 'cannot downgrade biw3_002 with observation receipts' USING ERRCODE='55000'; END IF;
        END $$"""
    )
    op.execute(f"DROP FUNCTION observation_receipt_record_biw3_002{RECORD_SIGNATURE}")
    op.execute("DROP TABLE business_investigation_observation_receipt")
