"""Add tenant-bound read-only observation session and plan authority.

Revision ID: biw3_001
Revises: biw2_004
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "biw3_001"
down_revision: str | Sequence[str] | None = "biw2_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ISSUE_SIGNATURE = "(text,text,text,jsonb)"
REVOKE_SIGNATURE = "(text,integer,text,text)"
PLAN_SIGNATURE = "(text,integer,text,text,jsonb)"


def _secure_function(name: str, signature: str) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {name}{signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {name}{signature} TO aos_runtime")


def _rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_biw3_001 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
    op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE business_investigation_observation_session_lease (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, lease_id TEXT NOT NULL,
          revision INTEGER NOT NULL DEFAULT 1, state_version INTEGER NOT NULL DEFAULT 1,
          content_hash TEXT NOT NULL, platform TEXT NOT NULL,
          requirement_id TEXT NOT NULL, requirement_revision BIGINT NOT NULL,
          requirement_content_hash TEXT NOT NULL,
          status TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          revocation_idempotency_key TEXT,
          authority_data JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,lease_id),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(revision=1), CHECK(state_version>=1),
          CHECK(status IN ('active','revoked')),
          CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(platform IN ('niushop','wechat_store','douyin_store')),
          FOREIGN KEY(org_id,project_id,requirement_id,requirement_revision)
            REFERENCES data_requirement_revision(org_id,project_id,requirement_id,revision)
        )"""
    )
    op.execute(
        """CREATE TABLE business_investigation_observation_plan_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, plan_id TEXT NOT NULL,
          current_revision BIGINT NOT NULL, current_content_hash TEXT NOT NULL,
          version INTEGER NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,plan_id),
          CHECK(current_revision>=1), CHECK(version>=1),
          CHECK(current_content_hash ~ '^sha256:[0-9a-f]{64}$')
        )"""
    )
    op.execute(
        """CREATE TABLE business_investigation_observation_plan_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, plan_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          lease_id TEXT NOT NULL, lease_revision INTEGER NOT NULL, lease_content_hash TEXT NOT NULL,
          requirement_id TEXT NOT NULL, requirement_revision BIGINT NOT NULL,
          requirement_content_hash TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          authority_data JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,plan_id,revision),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(revision>=1),
          CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(lease_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(requirement_content_hash ~ '^sha256:[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,lease_id)
            REFERENCES business_investigation_observation_session_lease(org_id,project_id,lease_id),
          FOREIGN KEY(org_id,project_id,requirement_id,requirement_revision)
            REFERENCES data_requirement_revision(org_id,project_id,requirement_id,revision)
        )"""
    )
    op.execute(
        "CREATE INDEX idx_observation_lease_expiry_biw3_001 ON business_investigation_observation_session_lease(org_id,project_id,status,expires_at)"
    )
    op.execute(
        "CREATE INDEX idx_observation_plan_lease_biw3_001 ON business_investigation_observation_plan_revision(org_id,project_id,lease_id,lease_revision)"
    )
    for table in (
        "business_investigation_observation_session_lease",
        "business_investigation_observation_plan_head",
        "business_investigation_observation_plan_revision",
    ):
        _rls(table)

    op.execute(
        """CREATE FUNCTION observation_lease_issue_biw3_001(
          p_lease_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb
        ) RETURNS TABLE(authority_data jsonb,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_existing record;
          v_requirement jsonb:=p_payload->'requirementRef';
          v_issued timestamptz; v_expires timestamptz;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_lease_id)='' OR btrim(p_idempotency_key)=''
             OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR p_payload IS NULL
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid tenant-bound observation lease'; END IF;
          SELECT l.authority_data,l.request_hash INTO v_existing
            FROM business_investigation_observation_session_lease l
           WHERE l.org_id=v_org AND l.project_id=v_project AND l.idempotency_key=p_idempotency_key;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash THEN
              RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='observation lease idempotency conflict'; END IF;
            RETURN QUERY SELECT v_existing.authority_data,true; RETURN;
          END IF;
          v_issued:=(p_payload->>'issuedAt')::timestamptz; v_expires:=(p_payload->>'expiresAt')::timestamptz;
          IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
             OR p_payload->>'leaseId'<>p_lease_id OR p_payload->>'schemaVersion'<>'aos.business-investigation.observation-session-lease/v1'
             OR p_payload->>'scope'<>'read-only-observation' OR p_payload->>'status'<>'active'
             OR (p_payload->>'revision')::integer<>1 OR (p_payload->>'stateVersion')::integer<>1
             OR p_payload->>'requestHash'<>p_request_hash OR v_expires<=v_issued
             OR v_expires>v_issued+interval '2 hours' OR v_expires<=NOW()
             OR p_payload->'sessionHandleRef'->>'resourceType'<>'ObservationSessionHandleRef'
             OR p_payload ?| ARRAY['cookie','password','captcha','token','localStorage','sessionPayload']
             OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(p_payload->'allowedDomains') d
                        WHERE char_length(d)>253 OR d !~ '^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$'
                           OR d LIKE '%..%' OR d LIKE '%.-%' OR d LIKE '%-.%')
             OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(p_payload->'allowedRoutePatterns') r
                        WHERE left(r,1)<>'/' OR r LIKE '%?%' OR r LIKE '%#%' OR r LIKE '%..%' OR r LIKE '%//%')
             OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(p_payload->'allowedReadActions') a
                        WHERE a NOT IN ('navigate','wait','scroll','filter','open-detail','read','export'))
             OR ((p_payload->'allowedReadActions') ? 'export')<>(p_payload->'exportAuthorizationRef' IS NOT NULL AND p_payload->'exportAuthorizationRef'<>'null'::jsonb)
             OR (((p_payload->'allowedReadActions') ? 'export') AND p_payload#>>'{exportAuthorizationRef,resourceType}'<>'ReadOnlyExportAuthorizationRevision')
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='observation lease violates read-only contract'; END IF;
          IF v_requirement->>'resourceType'<>'DataRequirementRevision' OR NOT EXISTS(
            SELECT 1 FROM data_requirement_head h WHERE h.org_id=v_org AND h.project_id=v_project
             AND h.requirement_id=v_requirement->>'resourceId'
             AND h.current_revision=(v_requirement->>'revision')::bigint
             AND ('sha256:'||h.current_content_hash)=v_requirement->>'contentHash'
          ) THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='lease requires current DataRequirement exact ref'; END IF;
          INSERT INTO business_investigation_observation_session_lease(
            org_id,project_id,lease_id,revision,state_version,content_hash,platform,
            requirement_id,requirement_revision,requirement_content_hash,status,expires_at,
            idempotency_key,request_hash,authority_data)
          VALUES(v_org,v_project,p_lease_id,1,1,p_payload->>'contentHash',p_payload->>'platform',
            v_requirement->>'resourceId',(v_requirement->>'revision')::bigint,v_requirement->>'contentHash',
            'active',v_expires,p_idempotency_key,p_request_hash,p_payload);
          RETURN QUERY SELECT p_payload,false;
        END $$"""
    )

    op.execute(
        """CREATE FUNCTION observation_lease_revoke_biw3_001(
          p_lease_id text,p_expected_state_version integer,p_idempotency_key text,p_reason text
        ) RETURNS TABLE(authority_data jsonb,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_row record; v_payload jsonb;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_lease_id)='' OR p_expected_state_version<1
             OR btrim(p_idempotency_key)='' OR btrim(p_reason)=''
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid tenant-bound observation revoke'; END IF;
          SELECT * INTO v_row FROM business_investigation_observation_session_lease l
           WHERE l.org_id=v_org AND l.project_id=v_project AND l.lease_id=p_lease_id FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='BO002',MESSAGE='observation lease not found'; END IF;
          IF v_row.status='revoked' AND v_row.revocation_idempotency_key=p_idempotency_key THEN
            RETURN QUERY SELECT v_row.authority_data,true; RETURN;
          END IF;
          IF v_row.status<>'active' OR v_row.state_version<>p_expected_state_version
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='stale observation lease state version'; END IF;
          v_payload:=jsonb_set(jsonb_set(jsonb_set(jsonb_set(v_row.authority_data,'{status}','"revoked"'),
            '{stateVersion}',to_jsonb(v_row.state_version+1)),'{revokedAt}',to_jsonb(NOW())),'{revocationReason}',to_jsonb(p_reason));
          UPDATE business_investigation_observation_session_lease SET status='revoked',
            state_version=state_version+1,revocation_idempotency_key=p_idempotency_key,
            authority_data=v_payload,updated_at=NOW()
           WHERE org_id=v_org AND project_id=v_project AND lease_id=p_lease_id;
          RETURN QUERY SELECT v_payload,false;
        END $$"""
    )

    op.execute(
        """CREATE FUNCTION observation_plan_publish_biw3_001(
          p_plan_id text,p_expected_version integer,p_idempotency_key text,p_request_hash text,p_payload jsonb
        ) RETURNS TABLE(authority_data jsonb,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_existing record;
          v_head record; v_lease record; v_lease_ref jsonb:=p_payload->'leaseRef';
          v_requirement jsonb:=p_payload->'requirementRef'; v_revision bigint;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_plan_id)='' OR p_expected_version<0
             OR btrim(p_idempotency_key)='' OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR p_payload IS NULL
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='invalid tenant-bound observation plan'; END IF;
          SELECT r.authority_data,r.request_hash INTO v_existing
            FROM business_investigation_observation_plan_revision r
           WHERE r.org_id=v_org AND r.project_id=v_project AND r.idempotency_key=p_idempotency_key;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash THEN
              RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='observation plan idempotency conflict'; END IF;
            RETURN QUERY SELECT v_existing.authority_data,true; RETURN;
          END IF;
          IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
             OR p_payload->>'planId'<>p_plan_id OR p_payload->>'schemaVersion'<>'aos.business-investigation.observation-plan/v1'
             OR p_payload->>'requestHash'<>p_request_hash
             OR v_lease_ref->>'resourceType'<>'ObservationSessionLeaseRevision'
             OR v_requirement->>'resourceType'<>'DataRequirementRevision'
             OR p_payload ?| ARRAY['cookie','password','captcha','token','localStorage','sessionPayload']
             OR NOT (p_payload->'prohibitedControls' ?& ARRAY['save','submit','delete','list','publish','ship','reprice','contact','sign','settle','batch','permission-config'])
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='observation plan violates exact contract'; END IF;
          SELECT * INTO v_lease FROM business_investigation_observation_session_lease l
           WHERE l.org_id=v_org AND l.project_id=v_project AND l.lease_id=v_lease_ref->>'resourceId' FOR SHARE;
          IF NOT FOUND OR v_lease.status<>'active' OR v_lease.expires_at<=NOW()
             OR v_lease.revision<>(v_lease_ref->>'revision')::integer OR v_lease.content_hash<>v_lease_ref->>'contentHash'
             OR v_lease.requirement_id<>v_requirement->>'resourceId'
             OR v_lease.requirement_revision<>(v_requirement->>'revision')::bigint
             OR v_lease.requirement_content_hash<>v_requirement->>'contentHash'
             OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'steps') s
               WHERE NOT (v_lease.authority_data->'allowedDomains' ? (s->>'domain'))
                  OR NOT (v_lease.authority_data->'allowedRoutePatterns' ? (s->>'routePattern'))
                  OR NOT (v_lease.authority_data->'allowedReadActions' ? (s->>'action')))
             OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'pageInventory') p
               WHERE NOT (v_lease.authority_data->'allowedDomains' ? (p->>'domain'))
                  OR NOT (v_lease.authority_data->'allowedRoutePatterns' ? (p->>'routePattern')))
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='observation plan exceeds current active lease'; END IF;
          IF NOT EXISTS(SELECT 1 FROM data_requirement_head h WHERE h.org_id=v_org AND h.project_id=v_project
             AND h.requirement_id=v_requirement->>'resourceId'
             AND h.current_revision=(v_requirement->>'revision')::bigint
             AND ('sha256:'||h.current_content_hash)=v_requirement->>'contentHash')
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='plan requires current DataRequirement exact ref'; END IF;
          SELECT * INTO v_head FROM business_investigation_observation_plan_head h
           WHERE h.org_id=v_org AND h.project_id=v_project AND h.plan_id=p_plan_id FOR UPDATE;
          v_revision:=(p_payload->>'revision')::bigint;
          IF NOT FOUND THEN
            IF p_expected_version<>0 OR v_revision<>1 OR p_payload->'priorRef'<>'null'::jsonb
            THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='invalid initial observation plan CAS'; END IF;
            INSERT INTO business_investigation_observation_plan_head(org_id,project_id,plan_id,current_revision,current_content_hash,version)
            VALUES(v_org,v_project,p_plan_id,1,p_payload->>'contentHash',1);
          ELSE
            IF v_head.version<>p_expected_version OR v_revision<>v_head.current_revision+1
               OR p_payload#>>'{priorRef,resourceType}'<>'ObservationPlanRevision'
               OR p_payload#>>'{priorRef,resourceId}'<>p_plan_id
               OR (p_payload#>>'{priorRef,revision}')::bigint<>v_head.current_revision
               OR p_payload#>>'{priorRef,contentHash}'<>v_head.current_content_hash
            THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='stale observation plan CAS'; END IF;
            UPDATE business_investigation_observation_plan_head SET current_revision=v_revision,
              current_content_hash=p_payload->>'contentHash',version=version+1,updated_at=NOW()
             WHERE org_id=v_org AND project_id=v_project AND plan_id=p_plan_id;
          END IF;
          INSERT INTO business_investigation_observation_plan_revision(
            org_id,project_id,plan_id,revision,content_hash,lease_id,lease_revision,lease_content_hash,
            requirement_id,requirement_revision,requirement_content_hash,idempotency_key,request_hash,authority_data)
          VALUES(v_org,v_project,p_plan_id,v_revision,p_payload->>'contentHash',v_lease.lease_id,v_lease.revision,v_lease.content_hash,
            v_lease.requirement_id,v_lease.requirement_revision,v_lease.requirement_content_hash,p_idempotency_key,p_request_hash,p_payload);
          RETURN QUERY SELECT p_payload,false;
        END $$"""
    )

    _secure_function("observation_lease_issue_biw3_001", ISSUE_SIGNATURE)
    _secure_function("observation_lease_revoke_biw3_001", REVOKE_SIGNATURE)
    _secure_function("observation_plan_publish_biw3_001", PLAN_SIGNATURE)


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM business_investigation_observation_session_lease LIMIT 1)
             OR EXISTS(SELECT 1 FROM business_investigation_observation_plan_head LIMIT 1)
             OR EXISTS(SELECT 1 FROM business_investigation_observation_plan_revision LIMIT 1)
          THEN RAISE EXCEPTION 'cannot downgrade biw3_001 with observation authority state' USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    op.execute(f"DROP FUNCTION observation_plan_publish_biw3_001{PLAN_SIGNATURE}")
    op.execute(f"DROP FUNCTION observation_lease_revoke_biw3_001{REVOKE_SIGNATURE}")
    op.execute(f"DROP FUNCTION observation_lease_issue_biw3_001{ISSUE_SIGNATURE}")
    op.execute("DROP TABLE business_investigation_observation_plan_revision")
    op.execute("DROP TABLE business_investigation_observation_plan_head")
    op.execute("DROP TABLE business_investigation_observation_session_lease")
