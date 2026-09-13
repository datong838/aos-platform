"""Empty configuration staging transport; no API submission authority."""
from alembic import op

revision = 'a0v_036'
down_revision = 'a0v_035'
branch_labels = depends_on = None


def upgrade():
    op.execute(r'''
    CREATE TABLE extension_runtime_configuration_stage_request (
      org_id text NOT NULL, project_id text NOT NULL, request_id uuid NOT NULL,
      subject text NOT NULL CHECK(length(subject) BETWEEN 1 AND 240 AND subject=btrim(subject) AND subject !~ '[[:cntrl:]]'),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160 AND idempotency_key=btrim(idempotency_key) AND idempotency_key !~ '[[:cntrl:]]'),
      installation_id uuid NOT NULL, generation uuid NOT NULL,
      installation_etag bigint NOT NULL CHECK(installation_etag>0),
      binding_revision bigint NOT NULL CHECK(binding_revision>0),
      request_json jsonb NOT NULL CHECK(jsonb_typeof(request_json)='object' AND octet_length(request_json::text)<=65536),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      state text NOT NULL DEFAULT 'requested' CHECK(state IN ('requested','succeeded','rejected','expired')),
      revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(), deadline timestamptz NOT NULL,
      completed_at timestamptz, result_json jsonb,
      failure_code text CHECK(failure_code ~ '^[A-Z][A-Z0-9_]{0,79}$'),
      PRIMARY KEY(org_id,project_id,request_id),
      UNIQUE(org_id,project_id,subject,idempotency_key),
      FOREIGN KEY(org_id,project_id,installation_id,generation)
        REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation),
      CHECK(deadline>created_at AND deadline<=created_at+interval '5 minutes'),
      CHECK((state='requested' AND completed_at IS NULL) OR (state<>'requested' AND completed_at IS NOT NULL)),
      CHECK((state='succeeded' AND result_json IS NOT NULL AND failure_code IS NULL)
         OR (state<>'succeeded' AND result_json IS NULL)),
      CHECK((state IN ('rejected','expired') AND failure_code IS NOT NULL)
         OR (state NOT IN ('rejected','expired') AND failure_code IS NULL))
    );
    CREATE INDEX extension_runtime_configuration_stage_pending
      ON extension_runtime_configuration_stage_request(org_id,project_id,created_at,request_id) WHERE state='requested';
    ALTER TABLE extension_runtime_configuration_stage_request ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_runtime_configuration_stage_request FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_runtime_configuration_stage_request
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));

    CREATE FUNCTION extension_runtime_configuration_stage_guard() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_request jsonb; v_target jsonb; v_ref jsonb; v_refs jsonb;
      v_count integer; v_distinct integer; v_revision bigint; v_etag bigint;
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'configuration request history is immutable'; END IF;
      IF NEW.org_id IS DISTINCT FROM current_setting('aos.org_id',true)
         OR NEW.project_id IS DISTINCT FROM current_setting('aos.project_id',true) THEN
        RAISE EXCEPTION 'configuration request scope differs';
      END IF;
      v_request=NEW.request_json;
      IF NOT (v_request ?& ARRAY['schemaVersion','action','target','roleRefs','policyRef','previousRef'])
         OR v_request-ARRAY['schemaVersion','action','target','roleRefs','policyRef','previousRef']<>'{}'::jsonb
         OR v_request->>'schemaVersion' IS DISTINCT FROM 'aos.runtime-configuration-stage/v1'
         OR v_request->>'action' IS DISTINCT FROM 'stage-configuration'
         OR jsonb_typeof(v_request->'target') IS DISTINCT FROM 'object'
         OR jsonb_typeof(v_request->'roleRefs') IS DISTINCT FROM 'array'
         OR jsonb_typeof(v_request->'policyRef') IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'configuration request shape differs';
      END IF;
      v_target=v_request->'target';
      IF jsonb_typeof(v_target->'installationEtag') IS DISTINCT FROM 'number'
         OR jsonb_typeof(v_target->'bindingRevision') IS DISTINCT FROM 'number'
         OR (v_target->>'installationEtag') !~ '^[1-9][0-9]*$'
         OR (v_target->>'bindingRevision') !~ '^[1-9][0-9]*$'
         OR v_target IS DISTINCT FROM jsonb_build_object('installationId',NEW.installation_id::text,
          'generation',NEW.generation::text,'installationEtag',NEW.installation_etag,'bindingRevision',NEW.binding_revision) THEN
        RAISE EXCEPTION 'configuration request target differs';
      END IF;
      v_refs=v_request->'roleRefs';
      IF jsonb_array_length(v_refs) NOT BETWEEN 1 AND 64 THEN RAISE EXCEPTION 'responsibility count differs'; END IF;
      SELECT count(*),count(DISTINCT value->>'id') INTO v_count,v_distinct FROM jsonb_array_elements(v_refs);
      IF v_count<>v_distinct THEN RAISE EXCEPTION 'responsibility identity differs'; END IF;
      FOR v_ref IN SELECT value FROM jsonb_array_elements(v_refs) LOOP
        IF v_ref->>'authority' IS DISTINCT FROM 'aip.responsibility_plan_revision' THEN
          RAISE EXCEPTION 'responsibility authority differs'; END IF;
      END LOOP;
      IF v_request->'policyRef'->>'authority' IS DISTINCT FROM 'aip.runtime_policy_revision' THEN
        RAISE EXCEPTION 'runtime policy authority differs'; END IF;
      FOR v_ref IN SELECT value FROM jsonb_array_elements(v_refs||jsonb_build_array(v_request->'policyRef')) LOOP
        IF jsonb_typeof(v_ref) IS DISTINCT FROM 'object'
           OR NOT (v_ref ?& ARRAY['authority','id','revision','hash'])
           OR v_ref-ARRAY['authority','id','revision','hash']<>'{}'::jsonb
           OR jsonb_typeof(v_ref->'id') IS DISTINCT FROM 'string'
           OR length(v_ref->>'id')=0 OR v_ref->>'id'<>btrim(v_ref->>'id')
           OR v_ref->>'id' ~ '[[:cntrl:]]' OR position('://' IN v_ref->>'id')>0
           OR jsonb_typeof(v_ref->'revision') IS DISTINCT FROM 'number'
           OR (v_ref->>'revision') !~ '^[1-9][0-9]*$'
           OR jsonb_typeof(v_ref->'hash') IS DISTINCT FROM 'string'
           OR (v_ref->>'hash') !~ '^sha256:[0-9a-f]{64}$' THEN
          RAISE EXCEPTION 'configuration source reference differs';
        END IF;
        v_revision=(v_ref->>'revision')::bigint;
      END LOOP;
      v_ref=v_request->'previousRef';
      IF v_ref<>'null'::jsonb THEN
        IF jsonb_typeof(v_ref) IS DISTINCT FROM 'object'
           OR NOT (v_ref ?& ARRAY['configurationId','revision','hash'])
           OR v_ref-ARRAY['configurationId','revision','hash']<>'{}'::jsonb
           OR jsonb_typeof(v_ref->'configurationId') IS DISTINCT FROM 'string'
           OR jsonb_typeof(v_ref->'revision') IS DISTINCT FROM 'number'
           OR (v_ref->>'revision') !~ '^[1-9][0-9]*$'
           OR jsonb_typeof(v_ref->'hash') IS DISTINCT FROM 'string'
           OR (v_ref->>'hash') !~ '^sha256:[0-9a-f]{64}$' THEN
          RAISE EXCEPTION 'configuration previous reference differs'; END IF;
        IF (v_ref->>'configurationId')::uuid::text IS DISTINCT FROM v_ref->>'configurationId' THEN
          RAISE EXCEPTION 'configuration previous identity differs'; END IF;
        v_revision=(v_ref->>'revision')::bigint;
      END IF;
      IF NEW.request_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(canonical_asset_registry_jsonb(
          jsonb_build_object('tenant',jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id),
            'subject',NEW.subject,'request',NEW.request_json)), 'UTF8')),'hex') THEN
        RAISE EXCEPTION 'configuration request digest differs'; END IF;
      IF TG_OP='INSERT' THEN
        IF NEW.state<>'requested' OR NEW.revision<>1 OR NEW.deadline<=clock_timestamp()
           OR NEW.created_at<clock_timestamp()-interval '5 seconds' OR NEW.created_at>clock_timestamp()+interval '5 seconds' THEN
          RAISE EXCEPTION 'configuration request initial state differs'; END IF;
        SELECT i.etag_version,b.revision INTO v_etag,v_revision FROM bundle_installation i
          JOIN extension_runtime_binding b USING(org_id,project_id,installation_id)
          WHERE i.org_id=NEW.org_id AND i.project_id=NEW.project_id AND i.installation_id=NEW.installation_id
            AND b.generation=NEW.generation FOR SHARE OF i,b;
        IF NOT FOUND OR v_etag IS DISTINCT FROM NEW.installation_etag OR v_revision IS DISTINCT FROM NEW.binding_revision THEN
          RAISE EXCEPTION 'configuration request target changed'; END IF;
        RETURN NEW;
      END IF;
      IF ROW(NEW.org_id,NEW.project_id,NEW.request_id,NEW.subject,NEW.idempotency_key,NEW.installation_id,
          NEW.generation,NEW.installation_etag,NEW.binding_revision,NEW.request_json,NEW.request_hash,NEW.created_at,NEW.deadline)
         IS DISTINCT FROM ROW(OLD.org_id,OLD.project_id,OLD.request_id,OLD.subject,OLD.idempotency_key,OLD.installation_id,
          OLD.generation,OLD.installation_etag,OLD.binding_revision,OLD.request_json,OLD.request_hash,OLD.created_at,OLD.deadline)
         OR OLD.state<>'requested' OR NEW.state='requested' OR NEW.revision<>OLD.revision+1 THEN
        RAISE EXCEPTION 'configuration request identity or terminal state is immutable'; END IF;
      IF NEW.completed_at IS NULL OR NEW.completed_at<NEW.created_at OR NEW.completed_at>clock_timestamp() THEN
        RAISE EXCEPTION 'configuration completion clock differs'; END IF;
      IF (NEW.state='expired' AND NEW.deadline>clock_timestamp())
          OR (NEW.state='succeeded' AND NEW.deadline<=clock_timestamp()) THEN
        RAISE EXCEPTION 'configuration deadline differs'; END IF;
      IF NEW.state='succeeded' THEN
        v_ref=NEW.result_json;
        IF jsonb_typeof(v_ref) IS DISTINCT FROM 'object'
           OR NOT (v_ref ?& ARRAY['configurationId','revision','hash'])
           OR v_ref-ARRAY['configurationId','revision','hash']<>'{}'::jsonb
           OR jsonb_typeof(v_ref->'configurationId') IS DISTINCT FROM 'string'
           OR jsonb_typeof(v_ref->'revision') IS DISTINCT FROM 'number'
           OR (v_ref->>'revision') !~ '^[1-9][0-9]*$'
           OR jsonb_typeof(v_ref->'hash') IS DISTINCT FROM 'string'
           OR (v_ref->>'hash') !~ '^sha256:[0-9a-f]{64}$' THEN
          RAISE EXCEPTION 'configuration result reference differs'; END IF;
        IF (v_ref->>'configurationId')::uuid::text IS DISTINCT FROM v_ref->>'configurationId' THEN
          RAISE EXCEPTION 'configuration result identity differs'; END IF;
        PERFORM 1 FROM extension_runtime_configuration WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND installation_id=NEW.installation_id AND generation=NEW.generation AND actor=NEW.subject
          AND configuration_id=(v_ref->>'configurationId')::uuid AND revision=(v_ref->>'revision')::bigint
          AND content_hash=v_ref->>'hash'
          AND idempotency_key='configuration-stage:'||NEW.request_id::text
          AND payload->'roleRefs'=NEW.request_json->'roleRefs'
          AND payload->'policyRef'=NEW.request_json->'policyRef'
          AND ((NEW.request_json->'previousRef'='null'::jsonb AND revision=1 AND previous_hash IS NULL)
            OR (NEW.request_json->'previousRef'<>'null'::jsonb
              AND configuration_id=(NEW.request_json->'previousRef'->>'configurationId')::uuid
              AND revision=(NEW.request_json->'previousRef'->>'revision')::bigint+1
              AND previous_hash=NEW.request_json->'previousRef'->>'hash'));
        IF NOT FOUND THEN RAISE EXCEPTION 'configuration result is not an exact owned record'; END IF;
      END IF;
      RETURN NEW;
    END;
    $$;
    CREATE TRIGGER configuration_stage_guard BEFORE INSERT OR UPDATE OR DELETE
      ON extension_runtime_configuration_stage_request FOR EACH ROW EXECUTE FUNCTION extension_runtime_configuration_stage_guard();
    CREATE TRIGGER configuration_stage_no_truncate BEFORE TRUNCATE
      ON extension_runtime_configuration_stage_request FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    REVOKE ALL ON extension_runtime_configuration_stage_request FROM PUBLIC,aos_runtime;
    GRANT SELECT ON extension_runtime_configuration_stage_request TO aos_runtime;
    GRANT UPDATE(state,revision,completed_at,result_json,failure_code)
      ON extension_runtime_configuration_stage_request TO aos_runtime;
    REVOKE ALL ON FUNCTION extension_runtime_configuration_stage_guard() FROM PUBLIC;
    ''')


def downgrade():
    raise RuntimeError('configuration staging history must be retained; forward only')
