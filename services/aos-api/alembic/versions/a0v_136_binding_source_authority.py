"""Add isolated source issuance/head and formal evaluation proof storage.

No legacy backfill, login provisioning, or command write grants. JSON checks
validate structure only; trusted commands must validate actual source authority.
"""
from alembic import op

revision = "a0v_136"
down_revision = "a0v_135"
branch_labels = depends_on = None


def upgrade() -> None:
    # Existing three-column PK already guarantees uniqueness. This redundant
    # index allows an exact revision+hash FK without rewriting source records.
    op.execute("""CREATE UNIQUE INDEX uq_aip_evidence_exact_license_source
        ON public.aip_evidence_bundle_revision
        (org_id,project_id,bundle_id,revision,content_hash)""")
    op.execute("""CREATE TABLE public.aip_license_source_issuance (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL,
        issuance_id TEXT NOT NULL CHECK (issuance_id=btrim(issuance_id) AND issuance_id<>''),
        bundle_id TEXT NOT NULL, revision BIGINT NOT NULL CHECK (revision>=1),
        content_hash TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
        installation_id UUID NOT NULL,
        installation_etag BIGINT NOT NULL CHECK (installation_etag>=1),
        receipt_id TEXT NOT NULL,
        owner_authorization_ref JSONB NOT NULL CHECK (
            jsonb_typeof(owner_authorization_ref)='object' AND owner_authorization_ref<>'{}'::jsonb),
        policy_ref JSONB NOT NULL CHECK (jsonb_typeof(policy_ref)='object' AND policy_ref<>'{}'::jsonb),
        issued_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (org_id,project_id,issuance_id),
        UNIQUE (org_id,project_id,issuance_id,bundle_id,revision,content_hash),
        CHECK (expires_at>issued_at),
        FOREIGN KEY (org_id,project_id,bundle_id,revision,content_hash)
            REFERENCES public.aip_evidence_bundle_revision(org_id,project_id,bundle_id,revision,content_hash),
        FOREIGN KEY (org_id,project_id,installation_id)
            REFERENCES public.bundle_installation(org_id,project_id,installation_id),
        FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES public.aip_agent_registry_receipt(org_id,project_id,receipt_id)
    )""")
    op.execute("""CREATE TABLE public.aip_license_source_head (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, bundle_id TEXT NOT NULL,
        revision BIGINT NOT NULL CHECK (revision>=1),
        content_hash TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
        issuance_id TEXT NOT NULL, epoch BIGINT NOT NULL CHECK (epoch>=0),
        PRIMARY KEY (org_id,project_id,bundle_id,revision,content_hash),
        FOREIGN KEY (org_id,project_id,issuance_id,bundle_id,revision,content_hash)
            REFERENCES public.aip_license_source_issuance
                (org_id,project_id,issuance_id,bundle_id,revision,content_hash)
    )""")
    op.execute("""CREATE TABLE public.aip_binding_evaluation_proof (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL,
        proof_id TEXT NOT NULL CHECK (proof_id=btrim(proof_id) AND proof_id<>''),
        proof_schema_version BIGINT NOT NULL DEFAULT 1 CHECK (proof_schema_version=1),
        binding_id TEXT NOT NULL, binding_version BIGINT NOT NULL CHECK (binding_version>=1),
        installation_id UUID NOT NULL,
        installation_etag BIGINT NOT NULL CHECK (installation_etag>=1),
        receipt_id TEXT NOT NULL,
        legacy_dependency_hash TEXT NOT NULL CHECK (legacy_dependency_hash ~ '^[0-9a-f]{64}$'),
        facts_hash TEXT NOT NULL CHECK (facts_hash ~ '^[0-9a-f]{64}$'),
        facts JSONB NOT NULL CHECK (jsonb_typeof(facts)='object'
            AND facts ?& ARRAY['Provider','Model','Policy','Route','Eval','Health','Capacity','Price']),
        checked_at TIMESTAMPTZ NOT NULL, valid_until TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (org_id,project_id,proof_id),
        UNIQUE (org_id,project_id,receipt_id),
        CHECK (valid_until>checked_at),
        FOREIGN KEY (org_id,project_id,binding_id)
            REFERENCES public.aip_capability_binding(org_id,project_id,binding_id),
        FOREIGN KEY (org_id,project_id,installation_id)
            REFERENCES public.bundle_installation(org_id,project_id,installation_id),
        FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES public.aip_agent_registry_receipt(org_id,project_id,receipt_id)
    )""")
    for table in ("aip_license_source_issuance", "aip_license_source_head",
                  "aip_binding_evaluation_proof"):
        # Names are static migration constants, never caller-controlled SQL.
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC,aos_runtime")
        op.execute(f"GRANT SELECT ON public.{table} TO aos_runtime")
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table} ON public.{table}
            FOR SELECT TO aos_runtime USING (
              org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        if table != "aip_license_source_head":
            op.execute(f"""CREATE TRIGGER trg_{table}_immutable
                BEFORE UPDATE OR DELETE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION public.guard_aip6_registry_append_only()""")
            op.execute(f"""CREATE TRIGGER trg_{table}_truncate_guard
                BEFORE TRUNCATE ON public.{table}
                FOR EACH STATEMENT EXECUTE FUNCTION public.guard_aip6_registry_append_only()""")


def downgrade() -> None:
    raise RuntimeError("formal source/proof history cannot be silently erased")
