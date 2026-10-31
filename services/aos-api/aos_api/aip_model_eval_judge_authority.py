"""Explicit pending-request SQL artifact; no formal migration or Action grant.

Install only through an independently authorized database owner. Runtime can
insert pending facts, so a future checker must rederive their original sources.
"""


def judge_request_statements() -> tuple[str, ...]:
    table = 'public.aip_model_eval_judge_request'
    return (
        f"""CREATE TABLE {table} (
          org_id text NOT NULL, project_id text NOT NULL,
          request_id text NOT NULL CHECK(length(request_id)>0),
          idempotency_key text NOT NULL CHECK(length(idempotency_key)>0),
          request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{{64}}$'),
          request_json jsonb NOT NULL, created_by text NOT NULL CHECK(length(created_by)>0),
          expires_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(org_id,project_id,request_id),
          UNIQUE(org_id,project_id,idempotency_key),
          FOREIGN KEY(org_id,project_id) REFERENCES public.twa_workspace(org_id,project_id),
          CHECK(expires_at>created_at),
          CHECK(request_hash=encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(request_json),'UTF8')),'hex')),
          CHECK((jsonb_typeof(request_json)='object'
            AND request_json->>'schemaVersion' IN ('aos.model-judge-call-request/v1','aos.model-judge-call-request/v2')
            AND (request_json->>'schemaVersion'='aos.model-judge-call-request/v1' OR
              (jsonb_typeof(request_json->'ruleFacts')='object'
               AND jsonb_typeof(request_json->'ruleFacts'->'source')='object'
               AND jsonb_typeof(request_json->'ruleFacts'->'rule')='object'
               AND request_json->'ruleFacts'->>'ruleHash' ~ '^[0-9a-f]{{64}}$'
               AND request_json->'ruleFacts'->'approvalAllowed'='false'::jsonb
               AND request_json->'ruleFacts'->'executionAllowed'='false'::jsonb))
            AND request_json->>'purpose'='model-judge-call'
            AND request_json->'executionAllowed'='false'::jsonb
            AND request_json->'tenant'->>'orgId'=org_id
            AND request_json->'tenant'->>'projectId'=project_id
            AND request_json->>'createdBy'=created_by
            AND (request_json->>'expiresAt')::timestamptz=expires_at) IS TRUE)
        )""",
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f"""CREATE POLICY tenant_scope_model_judge_pending ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))""",
        f"""CREATE TRIGGER model_judge_pending_append_only BEFORE UPDATE OR DELETE
          ON {table} FOR EACH ROW EXECUTE FUNCTION public.guard_aip4_append_only()""",
        f"""CREATE TRIGGER model_judge_pending_truncate_guard BEFORE TRUNCATE
          ON {table} FOR EACH STATEMENT EXECUTE FUNCTION public.guard_aip4_append_only()""",
        f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime',
        f'GRANT SELECT,INSERT ON {table} TO aos_runtime',
    )


def judge_action_metadata_statements() -> tuple[str,...]:
    """Explicit isolated Owner installation artifact, never runtime DDL."""
    return (
        """INSERT INTO meta_object_type(id,name,description,published,properties,required_markings)
        VALUES('ModelJudgeCallRequest','模型判读调用申请','仅供独立审批的不可执行申请',true,'[]'::jsonb,'[]'::jsonb)
        ON CONFLICT(id) DO NOTHING""",
        """INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria)
        VALUES('aip_request_model_judge_call','申请模型判读调用','ModelJudgeCallRequest','[]'::jsonb,'[]'::jsonb,'[]'::jsonb)
        ON CONFLICT(id) DO NOTHING""",
    )
