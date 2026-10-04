"""Preserve original build input without changing legacy evidence hashes."""
from alembic import op

revision = 'a0v_138'
down_revision = 'a0v_137'
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE public.aip_evidence_bundle_build_provenance (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL,
        bundle_id TEXT NOT NULL, revision BIGINT NOT NULL CHECK(revision>=1),
        content_hash TEXT NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
        operation TEXT NOT NULL DEFAULT 'evidence_bundle.build'
            CHECK(operation='evidence_bundle.build'),
        idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
        request_payload JSONB NOT NULL CHECK(jsonb_typeof(request_payload)='object'
            AND jsonb_typeof(request_payload->'requiredFactIds')='array'
            AND request_payload ? 'requiredFactIds'),
        authority_payload JSONB NOT NULL CHECK(jsonb_typeof(authority_payload)='object'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,bundle_id,revision,content_hash),
        UNIQUE(org_id,project_id,operation,idempotency_key),
        FOREIGN KEY(org_id,project_id,bundle_id,revision,content_hash)
            REFERENCES public.aip_evidence_bundle_revision
                (org_id,project_id,bundle_id,revision,content_hash),
        FOREIGN KEY(org_id,project_id,operation,idempotency_key)
            REFERENCES public.aip_production_contract_receipt
                (org_id,project_id,operation,idempotency_key)
    )""")
    op.execute('REVOKE ALL ON public.aip_evidence_bundle_build_provenance FROM PUBLIC,aos_runtime')
    op.execute('GRANT SELECT,INSERT ON public.aip_evidence_bundle_build_provenance TO aos_runtime')
    op.execute('ALTER TABLE public.aip_evidence_bundle_build_provenance ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.aip_evidence_bundle_build_provenance FORCE ROW LEVEL SECURITY')
    op.execute("""CREATE POLICY tenant_scope_evidence_build_provenance
        ON public.aip_evidence_bundle_build_provenance TO aos_runtime
        USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE TRIGGER trg_evidence_build_provenance_immutable
        BEFORE UPDATE OR DELETE ON public.aip_evidence_bundle_build_provenance
        FOR EACH ROW EXECUTE FUNCTION public.guard_aip6_registry_append_only()""")
    op.execute("""CREATE TRIGGER trg_evidence_build_provenance_truncate_guard
        BEFORE TRUNCATE ON public.aip_evidence_bundle_build_provenance
        FOR EACH STATEMENT EXECUTE FUNCTION public.guard_aip6_registry_append_only()""")


def downgrade() -> None:
    raise RuntimeError('original evidence build provenance cannot be erased')
