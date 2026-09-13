"""Add empty UI read transport, without granting enqueue or worker mutation rights."""
from alembic import op

revision='a0v_031'
down_revision='a0v_030'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    CREATE TABLE extension_runtime_ui_read_request (
      org_id text NOT NULL, project_id text NOT NULL, request_id uuid NOT NULL,
      subject text NOT NULL CHECK(length(subject) BETWEEN 1 AND 240 AND subject=btrim(subject) AND subject !~ '[[:cntrl:]]'),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 240),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      installation_id uuid NOT NULL, generation uuid NOT NULL,
      execution_epoch bigint NOT NULL CHECK(execution_epoch>0),
      operation_id text NOT NULL CHECK(operation_id='analyst_workspace_view_v1'),
      module_id text NOT NULL CHECK(module_id='ecommerce.analyst'),
      target_json jsonb NOT NULL CHECK(jsonb_typeof(target_json)='object'),
      case_limit integer NOT NULL CHECK(case_limit BETWEEN 1 AND 50),
      run_limit integer NOT NULL CHECK(run_limit BETWEEN 1 AND 10),
      state text NOT NULL CHECK(state IN ('requested','claimed','succeeded','denied','failed','expired')),
      revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      deadline timestamptz NOT NULL,
      claimed_at timestamptz, completed_at timestamptz,
      owner_token_hash text CHECK(owner_token_hash ~ '^sha256:[0-9a-f]{64}$'),
      attempt_id uuid,
      snapshot_hash text CHECK(snapshot_hash ~ '^sha256:[0-9a-f]{64}$'),
      attempt_request_hash text CHECK(attempt_request_hash ~ '^sha256:[0-9a-f]{64}$'),
      result_json jsonb CHECK(jsonb_typeof(result_json)='object' AND octet_length(result_json::text)<=900000),
      result_hash text CHECK(result_hash ~ '^sha256:[0-9a-f]{64}$'),
      failure_code text CHECK(failure_code ~ '^[A-Z][A-Z0-9_]{0,79}$'),
      PRIMARY KEY(org_id,project_id,request_id),
      UNIQUE(org_id,project_id,subject,idempotency_key),
      FOREIGN KEY(org_id,project_id,installation_id,generation)
        REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation),
      FOREIGN KEY(org_id,project_id,attempt_id)
        REFERENCES extension_runtime_execution_attempt(org_id,project_id,attempt_id),
      CHECK(deadline>created_at AND deadline<=created_at+interval '2 minutes'),
      CHECK((state IN ('requested','claimed') AND completed_at IS NULL)
         OR (state IN ('succeeded','denied','failed','expired') AND completed_at IS NOT NULL)),
      CHECK((state='succeeded' AND result_json IS NOT NULL AND result_hash IS NOT NULL AND failure_code IS NULL)
         OR (state<>'succeeded' AND result_json IS NULL AND result_hash IS NULL)),
      CHECK((state IN ('denied','failed','expired') AND failure_code IS NOT NULL)
         OR (state NOT IN ('denied','failed','expired') AND failure_code IS NULL)),
      CHECK((attempt_id IS NULL AND owner_token_hash IS NULL AND claimed_at IS NULL AND snapshot_hash IS NULL AND attempt_request_hash IS NULL)
         OR (attempt_id IS NOT NULL AND owner_token_hash IS NOT NULL AND claimed_at IS NOT NULL AND snapshot_hash IS NOT NULL AND attempt_request_hash IS NOT NULL)),
      CHECK(state NOT IN ('claimed','succeeded') OR attempt_id IS NOT NULL)
    );
    CREATE INDEX extension_runtime_ui_read_pending ON extension_runtime_ui_read_request(org_id,project_id,created_at,request_id)
      WHERE state='requested';
    ALTER TABLE extension_runtime_ui_read_request ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_runtime_ui_read_request FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_runtime_ui_read_request
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));

    CREATE FUNCTION extension_runtime_ui_read_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_attempt record; v_binding record;
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'UI read history is immutable'; END IF;
      IF NEW.org_id IS DISTINCT FROM current_setting('aos.org_id',true)
         OR NEW.project_id IS DISTINCT FROM current_setting('aos.project_id',true) THEN
        RAISE EXCEPTION 'UI read scope differs';
      END IF;
      IF NEW.target_json->>'installationId' IS DISTINCT FROM NEW.installation_id::text
         OR NEW.target_json->>'generation' IS DISTINCT FROM NEW.generation::text
         OR NEW.target_json->>'executionEpoch' IS DISTINCT FROM NEW.execution_epoch::text
         OR NEW.target_json-ARRAY['installationId','installationRevision','generation','executionEpoch','bindingRevision','route','resourceHash'] <> '{}'::jsonb
         OR NOT (NEW.target_json ?& ARRAY['installationId','installationRevision','generation','executionEpoch','bindingRevision','route','resourceHash'])
         OR NEW.target_json->>'route' IS DISTINCT FROM '/workshop/analyst'
         OR jsonb_typeof(NEW.target_json->'resourceHash') IS DISTINCT FROM 'string'
         OR jsonb_typeof(NEW.target_json->'installationRevision') IS DISTINCT FROM 'number'
         OR jsonb_typeof(NEW.target_json->'bindingRevision') IS DISTINCT FROM 'number'
         OR jsonb_typeof(NEW.target_json->'executionEpoch') IS DISTINCT FROM 'number'
         OR (NEW.target_json->>'resourceHash') !~ '^sha256:[0-9a-f]{64}$'
         OR (NEW.target_json->>'installationRevision') !~ '^[1-9][0-9]*$'
         OR (NEW.target_json->>'bindingRevision') !~ '^[1-9][0-9]*$' THEN
        RAISE EXCEPTION 'UI read target differs';
      END IF;
      IF NEW.request_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(canonical_asset_registry_jsonb(
        jsonb_build_object('tenant',jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id),'subject',NEW.subject,
          'request',jsonb_build_object('schemaVersion','aos.runtime-ui-read-request/v1','operationId',NEW.operation_id,
            'moduleId',NEW.module_id,'target',NEW.target_json,'caseLimit',NEW.case_limit,'runLimit',NEW.run_limit))
      ),'UTF8')),'hex') THEN RAISE EXCEPTION 'UI read request digest differs'; END IF;
      IF NEW.state='succeeded' AND NEW.result_hash IS DISTINCT FROM 'sha256:'||encode(
          sha256(convert_to(canonical_asset_registry_jsonb(NEW.result_json),'UTF8')),'hex') THEN
        RAISE EXCEPTION 'UI read result digest differs';
      END IF;
      IF TG_OP='INSERT' THEN
        IF NEW.state<>'requested' OR NEW.revision<>1 OR NEW.attempt_id IS NOT NULL
           OR NEW.completed_at IS NOT NULL OR NEW.deadline<=clock_timestamp()
           OR NEW.created_at<clock_timestamp()-interval '5 seconds'
           OR NEW.created_at>clock_timestamp()+interval '5 seconds' THEN
          RAISE EXCEPTION 'UI read initial state differs';
        END IF;
        SELECT enabled,operation_fence,execution_epoch,installation_revision,revision INTO v_binding FROM extension_runtime_binding
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND installation_id=NEW.installation_id AND generation=NEW.generation FOR SHARE;
        IF NOT FOUND OR v_binding.enabled IS DISTINCT FROM true OR v_binding.operation_fence IS DISTINCT FROM false
           OR v_binding.execution_epoch IS DISTINCT FROM NEW.execution_epoch
           OR v_binding.installation_revision::text IS DISTINCT FROM NEW.target_json->>'installationRevision'
           OR v_binding.revision::text IS DISTINCT FROM NEW.target_json->>'bindingRevision' THEN
          RAISE EXCEPTION 'UI read runtime unavailable';
        END IF;
        RETURN NEW;
      END IF;
      IF ROW(NEW.org_id,NEW.project_id,NEW.request_id,NEW.subject,NEW.idempotency_key,NEW.request_hash,
             NEW.installation_id,NEW.generation,NEW.execution_epoch,NEW.operation_id,NEW.module_id,NEW.target_json,
             NEW.case_limit,NEW.run_limit,NEW.created_at,NEW.deadline)
         IS DISTINCT FROM ROW(OLD.org_id,OLD.project_id,OLD.request_id,OLD.subject,OLD.idempotency_key,OLD.request_hash,
             OLD.installation_id,OLD.generation,OLD.execution_epoch,OLD.operation_id,OLD.module_id,OLD.target_json,
             OLD.case_limit,OLD.run_limit,OLD.created_at,OLD.deadline)
         OR OLD.state NOT IN ('requested','claimed') OR NEW.revision<>OLD.revision+1 THEN
        RAISE EXCEPTION 'UI read identity or terminal state is immutable';
      END IF;
      IF (OLD.state='requested' AND NEW.state NOT IN ('claimed','denied','expired'))
         OR (OLD.state='claimed' AND NEW.state NOT IN ('succeeded','failed','expired')) THEN
        RAISE EXCEPTION 'UI read transition differs';
      END IF;
      IF OLD.state='requested' AND NEW.state<>'claimed' AND NEW.attempt_id IS NOT NULL THEN
        RAISE EXCEPTION 'unclaimed UI read cannot attach an attempt';
      END IF;
      IF NEW.claimed_at IS NOT NULL AND (NEW.claimed_at<NEW.created_at OR NEW.claimed_at>clock_timestamp()) THEN
        RAISE EXCEPTION 'UI read claim clock differs';
      END IF;
      IF NEW.completed_at IS NOT NULL AND (NEW.completed_at<NEW.created_at OR NEW.completed_at>clock_timestamp()) THEN
        RAISE EXCEPTION 'UI read completion clock differs';
      END IF;
      IF OLD.state='claimed' AND ROW(NEW.attempt_id,NEW.owner_token_hash,NEW.claimed_at,NEW.snapshot_hash,NEW.attempt_request_hash)
         IS DISTINCT FROM ROW(OLD.attempt_id,OLD.owner_token_hash,OLD.claimed_at,OLD.snapshot_hash,OLD.attempt_request_hash) THEN
        RAISE EXCEPTION 'UI read claim is immutable';
      END IF;
      IF NEW.state IN ('claimed','succeeded') AND NEW.deadline<=clock_timestamp() THEN
        RAISE EXCEPTION 'UI read deadline expired';
      END IF;
      IF NEW.state='expired' AND NEW.deadline>clock_timestamp() THEN
        RAISE EXCEPTION 'UI read deadline is still current';
      END IF;
      IF NEW.attempt_id IS NOT NULL THEN
        SELECT installation_id,generation,execution_epoch,operation_kind,operation_key,request_hash,owner_token_hash,state
          INTO v_attempt FROM extension_runtime_execution_attempt
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND attempt_id=NEW.attempt_id FOR SHARE;
        IF NOT FOUND OR ROW(v_attempt.installation_id,v_attempt.generation,v_attempt.execution_epoch,v_attempt.operation_kind,
              v_attempt.operation_key,v_attempt.request_hash,v_attempt.owner_token_hash)
           IS DISTINCT FROM ROW(NEW.installation_id,NEW.generation,NEW.execution_epoch,'signed_read'::text,
              'ui-read:'||NEW.request_id::text,NEW.attempt_request_hash,NEW.owner_token_hash)
           OR (NEW.state='claimed' AND v_attempt.state<>'running')
           OR (NEW.state='succeeded' AND v_attempt.state<>'succeeded') THEN
          RAISE EXCEPTION 'UI read execution attempt differs';
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$;
    CREATE TRIGGER extension_runtime_ui_read_guard BEFORE INSERT OR UPDATE OR DELETE
      ON extension_runtime_ui_read_request FOR EACH ROW EXECUTE FUNCTION extension_runtime_ui_read_guard();
    REVOKE ALL ON extension_runtime_ui_read_request FROM PUBLIC;
    REVOKE ALL ON FUNCTION extension_runtime_ui_read_guard() FROM PUBLIC;
    GRANT SELECT ON extension_runtime_ui_read_request TO aos_runtime;
    ''')


def downgrade():
    raise RuntimeError('UI read history is retained; destructive downgrade is unsupported')
