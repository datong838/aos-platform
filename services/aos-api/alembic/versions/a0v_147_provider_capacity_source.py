"""Unverified physical capacity candidates only; no account or capacity publication."""
from alembic import op

revision='a0v_147'
down_revision='a0v_146'
branch_labels=depends_on=None


def upgrade():
    op.execute("""CREATE TABLE public.aip_provider_capacity_candidate (
      org_id text NOT NULL,project_id text NOT NULL,candidate_id text NOT NULL,
      candidate_kind text NOT NULL,revision bigint NOT NULL DEFAULT 1,
      idempotency_key text NOT NULL,content_hash text NOT NULL,
      request_json jsonb NOT NULL,created_by text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      authorization_mode text NOT NULL DEFAULT 'CANDIDATE_ONLY_NO_CAPACITY_NO_START',
      basis_verified boolean NOT NULL DEFAULT false,execution_allowed boolean NOT NULL DEFAULT false,
      PRIMARY KEY(org_id,project_id,candidate_id,revision),UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id) REFERENCES public.twa_workspace(org_id,project_id),
      CHECK(org_id='org-org' AND project_id='dev-project'),
      CHECK(candidate_kind IN ('account','basis') AND revision=1),
      CHECK(authorization_mode='CANDIDATE_ONLY_NO_CAPACITY_NO_START' AND NOT basis_verified AND NOT execution_allowed),
      CHECK(content_hash ~ '^[0-9a-f]{64}$' AND content_hash=encode(public.digest(convert_to(
        public.canonical_asset_registry_jsonb(request_json),'UTF8'),'sha256'),'hex')),
      CHECK((jsonb_typeof(request_json)='object'
        AND request_json - ARRAY['candidateKind','candidate','makerSubject']='{}'::jsonb
        AND request_json->>'candidateKind'=candidate_kind AND request_json->>'makerSubject'=created_by
        AND jsonb_typeof(request_json->'candidate')='object'
        AND request_json->'candidate'->'schemaVersion'='1'::jsonb
        AND request_json->'candidate'->'tenant'->>'orgId'=org_id
        AND request_json->'candidate'->'tenant'->>'projectId'=project_id) IS TRUE)
    )""")
    for kind,fields in (
        ('account',['schemaVersion','tenant','physicalAccountId','supplierId','supplierAccountFingerprint','providerRefs','evidenceRef']),
        ('basis',['schemaVersion','tenant','basisKind','physicalAccountRef','evidenceRef','maxConcurrency','tokenLimit','observedAt','validFrom','validUntil']),
    ):
        array='ARRAY['+','.join("'"+field+"'" for field in fields)+']'
        op.execute(f"ALTER TABLE public.aip_provider_capacity_candidate ADD CONSTRAINT capacity_candidate_{kind}_fields "
            f"CHECK(candidate_kind<>'{kind}' OR ((request_json->'candidate') ?& {array} "
            f"AND (request_json->'candidate') - {array}='{{}}'::jsonb) IS TRUE)")
    op.execute('ALTER TABLE public.aip_provider_capacity_candidate ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.aip_provider_capacity_candidate FORCE ROW LEVEL SECURITY')
    op.execute("""CREATE POLICY capacity_candidate_tenant ON public.aip_provider_capacity_candidate TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE TRIGGER capacity_candidate_append_only BEFORE UPDATE OR DELETE
      ON public.aip_provider_capacity_candidate FOR EACH ROW EXECUTE FUNCTION public.guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER capacity_candidate_truncate_guard BEFORE TRUNCATE
      ON public.aip_provider_capacity_candidate FOR EACH STATEMENT EXECUTE FUNCTION public.guard_aip4_append_only()""")
    op.execute('REVOKE ALL ON public.aip_provider_capacity_candidate FROM PUBLIC,aos_runtime')
    op.execute('GRANT SELECT,INSERT ON public.aip_provider_capacity_candidate TO aos_runtime')


def downgrade():
    raise RuntimeError('Capacity candidate evidence cannot be silently removed')
