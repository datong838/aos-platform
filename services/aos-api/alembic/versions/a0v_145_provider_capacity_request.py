"""Immutable nonexecuting Provider allocation requests, no capacity activation."""
from alembic import op
revision = 'a0v_145'
down_revision = 'a0v_144'
branch_labels = depends_on = None


def upgrade():
    # Match Python str.strip() rather than PostgreSQL's default space-only trim.
    strip_chars = "||".join(f"chr({point})" for point in
        [9,10,11,12,13,28,29,30,31,32,133,160,5760,*range(8192,8203),8232,8233,8239,8287,12288])
    table_sql = """CREATE TABLE public.aip_provider_capacity_request (
      org_id text NOT NULL, project_id text NOT NULL,
      request_id text NOT NULL, idempotency_key text NOT NULL,
      request_hash text NOT NULL, request_json jsonb NOT NULL,
      created_by text NOT NULL, expires_at timestamptz NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      authorization_mode text NOT NULL DEFAULT 'REQUEST_ONLY_NO_CAPACITY_NO_START',
      basis_verified boolean NOT NULL DEFAULT false,
      execution_allowed boolean NOT NULL DEFAULT false,
      PRIMARY KEY(org_id,project_id,request_id),
      UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id) REFERENCES public.twa_workspace(org_id,project_id),
      CHECK(request_id<>'' AND request_id=btrim(request_id) AND length(request_id)<=200),
      CHECK(idempotency_key<>'' AND idempotency_key=btrim(idempotency_key) AND length(idempotency_key)<=200),
      CHECK(created_by<>'' AND created_by=btrim(created_by) AND length(created_by)<=200),
      CHECK(authorization_mode='REQUEST_ONLY_NO_CAPACITY_NO_START' AND NOT basis_verified AND NOT execution_allowed),
      CHECK(request_hash ~ '^[0-9a-f]{64}$' AND request_hash=encode(public.digest(
        convert_to(public.canonical_asset_registry_jsonb(request_json),'UTF8'),'sha256'),'hex')),
      CHECK((jsonb_typeof(request_json)='object'
        AND request_json->>'makerSubject'=created_by
        AND request_json->'application'->'tenant'->>'orgId'=org_id
        AND request_json->'application'->'tenant'->>'projectId'=project_id
        AND request_json->'application'->>'basisKind'='owner_requested_allocation'
        AND request_json->'application'->>'tokenUnit'='token'
        AND (request_json->'application'->>'proposalExpiresAt')::timestamptz=expires_at
        AND (request_json->'application'->>'validFrom')::timestamptz<=created_at
        AND (request_json->'application'->>'validUntil')::timestamptz>=expires_at) IS TRUE),
      CHECK(expires_at>created_at AND expires_at<=created_at+interval '15 minutes')
    )"""
    for field in ('request_id','idempotency_key','created_by'):
        table_sql = table_sql.replace(f"btrim({field})",f"btrim({field},{strip_chars})")
    op.execute(table_sql)
    # A runtime INSERT is not allowed to bypass the strict application envelope.
    app = "(request_json->'application')"
    checks = [
        "org_id='org-org' AND project_id='dev-project'",
        "request_json - ARRAY['application','makerSubject'] = '{}'::jsonb",
        "jsonb_typeof(request_json->'makerSubject')='string'",
        f"jsonb_typeof({app})='object'",
        f"{app} - ARRAY['schemaVersion','tenant','providerRef','physicalAccountId',"
        "'requestedMaxConcurrency','requestedMaxTokenUnits','tokenUnit','basisKind',"
        "'basisEvidenceRef','validFrom','validUntil','proposalExpiresAt'] = '{}'::jsonb",
        f"jsonb_typeof({app}->'schemaVersion')='number' AND {app}->>'schemaVersion'='1'",
        f"jsonb_typeof({app}->'tenant')='object' AND ({app}->'tenant') - ARRAY['orgId','projectId']='{{}}'::jsonb",
        f"jsonb_typeof({app}->'tenant'->'orgId')='string' AND jsonb_typeof({app}->'tenant'->'projectId')='string'",
        f"jsonb_typeof({app}->'physicalAccountId')='string' AND length({app}->>'physicalAccountId') BETWEEN 1 AND 200 "
        f"AND {app}->>'physicalAccountId'=btrim({app}->>'physicalAccountId',{strip_chars})",
        f"jsonb_typeof({app}->'tokenUnit')='string' AND jsonb_typeof({app}->'basisKind')='string'",
    ]
    for field, maximum in (('requestedMaxConcurrency',1000000),('requestedMaxTokenUnits',1000000000000)):
        checks.append(f"CASE WHEN jsonb_typeof({app}->'{field}')='number' THEN "
                      f"{app}->>'{field}' ~ '^[1-9][0-9]*$' AND ({app}->>'{field}')::numeric<={maximum} ELSE false END")
    for field, kind in (('providerRef','ProviderInstanceRevision'),('basisEvidenceRef','EvidenceBundleRevision')):
        ref = f"({app}->'{field}')"
        checks.extend([
            f"jsonb_typeof({ref})='object' AND {ref} - ARRAY['assetType','assetId','revision','contentHash']='{{}}'::jsonb",
            f"jsonb_typeof({ref}->'assetType')='string' AND {ref}->>'assetType'='{kind}'",
            f"jsonb_typeof({ref}->'assetId')='string' AND length({ref}->>'assetId') BETWEEN 1 AND 200 "
            f"AND {ref}->>'assetId'=btrim({ref}->>'assetId',{strip_chars})",
            f"jsonb_typeof({ref}->'revision')='number' AND {ref}->>'revision' ~ '^[1-9][0-9]*$'",
            f"jsonb_typeof({ref}->'contentHash')='string' AND {ref}->>'contentHash' ~ '^[0-9a-f]{{64}}$'",
        ])
    for field in ('validFrom','validUntil','proposalExpiresAt'):
        checks.append(f"jsonb_typeof({app}->'{field}')='string' AND {app}->>'{field}' ~ '(Z|[+-][0-9]{{2}}:[0-9]{{2}})$'")
    checks.append(f"({app}->>'validFrom')::timestamptz<expires_at AND "
                  f"({app}->>'validUntil')::timestamptz-({app}->>'validFrom')::timestamptz<=interval '366 days'")
    op.execute("ALTER TABLE public.aip_provider_capacity_request ADD CONSTRAINT provider_capacity_request_strict_application "
               "CHECK ((" + " AND ".join(f"({check})" for check in checks) + ") IS TRUE)")
    op.execute('ALTER TABLE public.aip_provider_capacity_request ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.aip_provider_capacity_request FORCE ROW LEVEL SECURITY')
    op.execute("""CREATE POLICY tenant_scope_provider_capacity_request_a145
      ON public.aip_provider_capacity_request TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
         AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
         AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE TRIGGER provider_capacity_request_append_only
      BEFORE UPDATE OR DELETE ON public.aip_provider_capacity_request
      FOR EACH ROW EXECUTE FUNCTION public.guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER provider_capacity_request_truncate_guard
      BEFORE TRUNCATE ON public.aip_provider_capacity_request
      FOR EACH STATEMENT EXECUTE FUNCTION public.guard_aip4_append_only()""")
    op.execute('REVOKE ALL ON public.aip_provider_capacity_request FROM PUBLIC,aos_runtime')
    op.execute('GRANT SELECT,INSERT ON public.aip_provider_capacity_request TO aos_runtime')


def downgrade():
    raise RuntimeError('Provider allocation request evidence cannot be silently removed')
