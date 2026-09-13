"""Atomically store disabled product event policy and its exact Case successor."""
from alembic import op

revision = 'a0v_040'
down_revision = 'a0v_039'
branch_labels = depends_on = None
SIGNATURE = '(text,bigint,bigint,text,jsonb,jsonb)'
NAME = 'ecommerce_product_event_policy_put_a0v_040'


def upgrade():
    op.execute(r"""CREATE FUNCTION ecommerce_product_event_policy_put_a0v_040(
      p_idempotency_key text,p_expected_policy_revision bigint,p_expected_case_version bigint,
      p_request_hash text,p_policy jsonb,p_case jsonb)
      RETURNS TABLE(policy_authority jsonb,case_authority jsonb,replayed boolean)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE
        v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        p_schedule_policy_id text:=p_policy->>'schedulePolicyId';
        p_case_id text:=p_case->>'caseId';
        v_case_head record;v_case_prior record;v_policy_head record;v_policy_prior record;
        v_existing record;v_ref jsonb;v_name text;v_kind text;v_text text;
        v_created timestamptz;v_start timestamptz;v_end timestamptz;v_stamp timestamp;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL
          OR (p_expected_policy_revision BETWEEN 0 AND 9223372036854775806) IS NOT TRUE
          OR (p_expected_case_version BETWEEN 1 AND 9223372036854775806) IS NOT TRUE
          OR (length(p_idempotency_key) BETWEEN 1 AND 200 AND btrim(p_idempotency_key)=p_idempotency_key) IS NOT TRUE
          OR jsonb_typeof(p_policy) IS DISTINCT FROM 'object'
          OR jsonb_typeof(p_case) IS DISTINCT FROM 'object'
        THEN RAISE EXCEPTION 'event policy request invalid' USING ERRCODE='23514'; END IF;
        IF (SELECT array_agg(k ORDER BY k COLLATE "C") FROM jsonb_object_keys(p_policy) k)
          IS DISTINCT FROM ARRAY['caseRef','contentHash','createdAt','createdBy','effectiveFrom','effectiveUntil',
          'maxSourceAgeSeconds','methodRef','objectTypes','platform','priorRef','recoveryWindowSeconds',
          'revision','schedulePolicyId','schemaVersion','shopId','sourceSelectionRef','tenant']::text[]
          OR p_policy->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.product-event-schedule-policy/v1'
          OR p_policy->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',v_org,'projectId',v_project)
          OR p_case->'tenant' IS DISTINCT FROM p_policy->'tenant'
          OR p_policy->'revision' IS DISTINCT FROM to_jsonb(p_expected_policy_revision+1)
          OR p_case->'revision' IS DISTINCT FROM to_jsonb(p_expected_case_version+1)
          OR p_case->'version' IS DISTINCT FROM to_jsonb(p_expected_case_version+1)
          OR p_request_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(jsonb_build_object('policy',p_policy,'case',p_case)),'UTF8')),'hex')
          OR p_policy->>'contentHash' IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(p_policy-'contentHash'),'UTF8')),'hex')
          OR p_case->>'contentHash' IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(p_case-'contentHash'),'UTF8')),'hex')
        THEN RAISE EXCEPTION 'event policy identity or digest invalid' USING ERRCODE='23514'; END IF;
        FOREACH v_name IN ARRAY ARRAY['schedulePolicyId','shopId','createdBy'] LOOP
          v_text:=p_policy->>v_name;
          IF jsonb_typeof(p_policy->v_name) IS DISTINCT FROM 'string'
            OR (length(v_text) BETWEEN 1 AND 200 AND v_text=btrim(v_text)
                AND v_text<>'*' AND v_text !~ '[[:cntrl:]]') IS NOT TRUE
          THEN RAISE EXCEPTION 'event policy text invalid' USING ERRCODE='23514'; END IF;
        END LOOP;
        IF (p_policy->>'platform' ~ '^[a-z][a-z0-9_.-]{0,63}$') IS NOT TRUE
          OR p_policy->'objectTypes' NOT IN ('["Product"]'::jsonb,'["ProductSku"]'::jsonb,'["Product","ProductSku"]'::jsonb)
        THEN RAISE EXCEPTION 'event policy source vocabulary invalid' USING ERRCODE='23514'; END IF;
        FOREACH v_name IN ARRAY ARRAY['maxSourceAgeSeconds','recoveryWindowSeconds','revision'] LOOP
          IF jsonb_typeof(p_policy->v_name) IS DISTINCT FROM 'number'
            OR (p_policy->>v_name ~ '^[1-9][0-9]*$') IS NOT TRUE
          THEN RAISE EXCEPTION 'event policy integer invalid' USING ERRCODE='23514'; END IF;
        END LOOP;
        IF ((p_policy->>'maxSourceAgeSeconds')::numeric BETWEEN 1 AND 86400
          AND (p_policy->>'recoveryWindowSeconds')::numeric BETWEEN 1 AND 86400) IS NOT TRUE
        THEN RAISE EXCEPTION 'event policy window invalid' USING ERRCODE='23514'; END IF;
        FOREACH v_name IN ARRAY ARRAY['createdAt','effectiveFrom','effectiveUntil'] LOOP
          IF (p_policy->>v_name ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{6})?\+00:00$') IS NOT TRUE
          THEN RAISE EXCEPTION 'event policy UTC invalid' USING ERRCODE='23514'; END IF;
        END LOOP;
        BEGIN
          v_created:=(p_policy->>'createdAt')::timestamptz;
          v_start:=(p_policy->>'effectiveFrom')::timestamptz;
          v_end:=(p_policy->>'effectiveUntil')::timestamptz;
        EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
          RAISE EXCEPTION 'event policy UTC invalid' USING ERRCODE='23514';
        END;
        FOREACH v_name IN ARRAY ARRAY['createdAt','effectiveFrom','effectiveUntil'] LOOP
          v_stamp:=(p_policy->>v_name)::timestamptz AT TIME ZONE 'UTC';
          v_text:=to_char(v_stamp,'YYYY-MM-DD"T"HH24:MI:SS')
            ||CASE WHEN to_char(v_stamp,'US')='000000' THEN '' ELSE '.'||to_char(v_stamp,'US') END||'+00:00';
          IF p_policy->>v_name IS DISTINCT FROM v_text THEN
            RAISE EXCEPTION 'event policy noncanonical UTC' USING ERRCODE='23514'; END IF;
        END LOOP;
        IF (v_created<=v_start AND v_start<v_end AND v_end-v_start<=interval '1 day') IS NOT TRUE
        THEN RAISE EXCEPTION 'event policy time order invalid' USING ERRCODE='23514'; END IF;
        FOREACH v_name IN ARRAY ARRAY['caseRef','sourceSelectionRef','methodRef','priorRef'] LOOP
          IF v_name='priorRef' AND p_expected_policy_revision=0 THEN
            IF p_policy->v_name IS DISTINCT FROM 'null'::jsonb THEN
              RAISE EXCEPTION 'event policy first prior invalid' USING ERRCODE='23514'; END IF;
            CONTINUE;
          END IF;
          v_ref:=p_policy->v_name;
          v_kind:=CASE v_name WHEN 'caseRef' THEN 'BusinessInvestigationCaseRevision'
            WHEN 'sourceSelectionRef' THEN 'SourceSelectionRevision'
            WHEN 'methodRef' THEN 'InvestigationProfileRevision' ELSE 'SchedulePolicyRevision' END;
          IF jsonb_typeof(v_ref) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'event policy exact ref invalid' USING ERRCODE='23514'; END IF;
          IF (SELECT array_agg(k ORDER BY k COLLATE "C") FROM jsonb_object_keys(v_ref) k)
              IS DISTINCT FROM ARRAY['contentHash','receiptId','resourceId','resourceType','revision']::text[]
            OR v_ref->>'resourceType' IS DISTINCT FROM v_kind
            OR v_ref->'receiptId' IS DISTINCT FROM 'null'::jsonb
            OR jsonb_typeof(v_ref->'resourceId') IS DISTINCT FROM 'string'
            OR (length(v_ref->>'resourceId') BETWEEN 1 AND 240
              AND btrim(v_ref->>'resourceId')=v_ref->>'resourceId'
              AND v_ref->>'resourceId'<>'*' AND v_ref->>'resourceId' !~ '[[:cntrl:]]') IS NOT TRUE
            OR jsonb_typeof(v_ref->'revision') IS DISTINCT FROM 'number'
            OR (v_ref->>'revision' ~ '^[1-9][0-9]*$') IS NOT TRUE
            OR (v_ref->>'contentHash' ~ '^sha256:[0-9a-f]{64}$') IS NOT TRUE
          THEN RAISE EXCEPTION 'event policy exact ref invalid' USING ERRCODE='23514'; END IF;
          IF (v_ref->>'revision')::numeric>9223372036854775807 THEN
            RAISE EXCEPTION 'event policy exact ref overflow' USING ERRCODE='23514'; END IF;
        END LOOP;
        SELECT * INTO v_case_head FROM public.ecommerce_investigation_case_head h
          WHERE h.org_id=v_org AND h.project_id=v_project AND h.case_id=p_case_id FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'event Case unavailable' USING ERRCODE='23514'; END IF;
        SELECT * INTO v_policy_head FROM public.ecommerce_investigation_schedule_policy_head h
          WHERE h.org_id=v_org AND h.project_id=v_project AND h.schedule_policy_id=p_schedule_policy_id FOR UPDATE;
        SELECT * INTO v_existing FROM public.ecommerce_investigation_schedule_policy_command_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project
          AND r.operation='business_investigation_schedule_policy.put' AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN
          IF v_existing.request_hash IS DISTINCT FROM p_request_hash
            OR v_existing.expected_policy_revision IS DISTINCT FROM p_expected_policy_revision
            OR v_existing.expected_case_version IS DISTINCT FROM p_expected_case_version
            OR v_existing.schedule_policy_id IS DISTINCT FROM p_schedule_policy_id
            OR v_existing.case_id IS DISTINCT FROM p_case_id
          THEN RAISE EXCEPTION 'event idempotency conflict' USING ERRCODE='23514'; END IF;
          RETURN QUERY SELECT v_existing.policy_authority,v_existing.case_authority,true; RETURN;
        END IF;
        IF v_case_head.version IS DISTINCT FROM p_expected_case_version
          OR v_case_head.current_revision IS DISTINCT FROM p_expected_case_version
          OR v_case_head.lifecycle IS DISTINCT FROM 'ACTIVE'
          OR (p_expected_policy_revision=0 AND v_policy_head.current_revision IS NOT NULL)
          OR (p_expected_policy_revision>0 AND v_policy_head.current_revision IS DISTINCT FROM p_expected_policy_revision)
        THEN RAISE EXCEPTION 'event expected version conflict' USING ERRCODE='23514'; END IF;
        SELECT * INTO v_case_prior FROM public.ecommerce_investigation_case_revision r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.case_id=p_case_id
          AND r.revision=p_expected_case_version;
        IF NOT FOUND THEN RAISE EXCEPTION 'event Case revision unavailable' USING ERRCODE='23514'; END IF;
        IF p_policy->'caseRef' IS DISTINCT FROM jsonb_build_object('resourceType','BusinessInvestigationCaseRevision',
            'resourceId',p_case_id,'revision',p_expected_case_version,'contentHash',v_case_prior.content_hash,'receiptId',NULL)
          OR p_policy->'methodRef' IS DISTINCT FROM v_case_prior.authority_data->'investigationProfileRef'
          OR p_case->'priorRef' IS DISTINCT FROM p_policy->'caseRef'
          OR p_case->'schedulePolicyRef' IS DISTINCT FROM jsonb_build_object('resourceType','SchedulePolicyRevision',
            'resourceId',p_schedule_policy_id,'revision',p_expected_policy_revision+1,'contentHash',p_policy->>'contentHash','receiptId',NULL)
          OR (p_case-ARRAY['revision','version','priorRef','contentHash','schedulePolicyRef','createdBy','createdAt'])
            IS DISTINCT FROM (v_case_prior.authority_data-ARRAY['revision','version','priorRef','contentHash','schedulePolicyRef','createdBy','createdAt'])
          OR p_case->>'createdBy' IS DISTINCT FROM p_policy->>'createdBy'
          OR p_case->>'createdAt' IS DISTINCT FROM replace(p_policy->>'createdAt','+00:00','Z')
          OR v_created<v_case_prior.created_at
        THEN RAISE EXCEPTION 'event Case binding invalid' USING ERRCODE='23514'; END IF;
        IF p_expected_policy_revision=0 THEN
          IF v_case_prior.authority_data->'schedulePolicyRef' IS DISTINCT FROM 'null'::jsonb THEN
            RAISE EXCEPTION 'event Case already bound' USING ERRCODE='23514'; END IF;
        ELSE
          SELECT * INTO v_policy_prior FROM public.ecommerce_investigation_schedule_policy_revision r
            WHERE r.org_id=v_org AND r.project_id=v_project AND r.schedule_policy_id=p_schedule_policy_id
              AND r.revision=p_expected_policy_revision;
          IF NOT FOUND THEN RAISE EXCEPTION 'event prior missing' USING ERRCODE='23514'; END IF;
          IF v_policy_prior.authority_data->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.product-event-schedule-policy/v1'
            OR v_policy_prior.case_id IS DISTINCT FROM p_case_id
            OR p_policy->'priorRef' IS DISTINCT FROM jsonb_build_object('resourceType','SchedulePolicyRevision',
              'resourceId',p_schedule_policy_id,'revision',p_expected_policy_revision,'contentHash',v_policy_prior.content_hash,'receiptId',NULL)
            OR v_case_prior.authority_data->'schedulePolicyRef' IS DISTINCT FROM p_policy->'priorRef'
            OR v_created<v_policy_prior.created_at
            OR v_start<(v_policy_prior.authority_data->>'effectiveFrom')::timestamptz
          THEN RAISE EXCEPTION 'event prior binding invalid' USING ERRCODE='23514'; END IF;
        END IF;
        INSERT INTO ecommerce_investigation_schedule_policy_revision(
          org_id,project_id,schedule_policy_id,revision,prior_revision,case_id,case_revision,
          analysis_type,policy_kind,cadence,enabled,content_hash,authority_data,created_by,created_at)
        VALUES(v_org,v_project,p_schedule_policy_id,p_expected_policy_revision+1,
          NULLIF(p_expected_policy_revision,0),p_case_id,p_expected_case_version,v_case_prior.analysis_type,
          'product_event','event',false,
          p_policy->>'contentHash',p_policy,p_policy->>'createdBy',(p_policy->>'createdAt')::timestamptz);
        IF p_expected_policy_revision=0 THEN
          INSERT INTO ecommerce_investigation_schedule_policy_head(
            org_id,project_id,schedule_policy_id,current_revision,case_id,analysis_type,enabled,
            content_hash,authority_data,updated_at)
          VALUES(v_org,v_project,p_schedule_policy_id,1,p_case_id,v_case_prior.analysis_type,
            false,p_policy->>'contentHash',p_policy,(p_policy->>'createdAt')::timestamptz);
        ELSE
          UPDATE ecommerce_investigation_schedule_policy_head SET current_revision=p_expected_policy_revision+1,
            enabled=false,content_hash=p_policy->>'contentHash',
            authority_data=p_policy,updated_at=(p_policy->>'createdAt')::timestamptz
          WHERE org_id=v_org AND project_id=v_project AND schedule_policy_id=p_schedule_policy_id;
        END IF;
        INSERT INTO ecommerce_investigation_case_revision(
          org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,
          analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,
          request_hash,authority_data,created_by,created_at)
        VALUES(v_org,v_project,p_case_id,p_expected_case_version+1,p_expected_case_version+1,
          p_expected_case_version,p_case->>'contentHash',v_case_prior.lifecycle,v_case_prior.analysis_type,
          v_case_prior.channel_id,v_case_prior.business_entity_id,v_case_prior.entity_channel_binding_id,
          p_idempotency_key,p_request_hash,p_case,p_case->>'createdBy',(p_case->>'createdAt')::timestamptz);
        UPDATE ecommerce_investigation_case_head SET current_revision=p_expected_case_version+1,
          version=p_expected_case_version+1,updated_at=(p_case->>'createdAt')::timestamptz
        WHERE org_id=v_org AND project_id=v_project AND case_id=p_case_id;
        INSERT INTO ecommerce_investigation_schedule_policy_command_receipt(
          org_id,project_id,receipt_id,operation,idempotency_key,request_hash,schedule_policy_id,
          expected_policy_revision,result_policy_revision,case_id,expected_case_version,
          result_case_revision,policy_authority,case_authority)
        VALUES(v_org,v_project,gen_random_uuid()::text,'business_investigation_schedule_policy.put',
          p_idempotency_key,p_request_hash,p_schedule_policy_id,p_expected_policy_revision,
          p_expected_policy_revision+1,p_case_id,p_expected_case_version,p_expected_case_version+1,p_policy,p_case);
        RETURN QUERY SELECT p_policy,p_case,false;
      END $$""")
    op.execute(f'REVOKE ALL ON FUNCTION {NAME}{SIGNATURE} FROM PUBLIC')
    op.execute(f'GRANT EXECUTE ON FUNCTION {NAME}{SIGNATURE} TO aos_runtime')


def downgrade():
    op.execute(f'DROP FUNCTION {NAME}{SIGNATURE}')
