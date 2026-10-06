"""Immutable independently signed documents; never a Source or execution grant."""
from aos_api.aip_provider_capacity_publication_registry import OWNER, PUBLISHER, SCHEMA
from aos_api.aip_provider_capacity_publication_store import (
    CAPACITY_SOURCE_POLICY_PROFILE_SQL, CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL,
)


DOCUMENT_TABLES = ('document',)

DOCUMENT_SQL = r"""
CREATE TABLE aos_capacity_publication_private.document(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 kind text NOT NULL CHECK(kind IN ('ProviderCapacitySourcePolicyRevision','SupplierCapacityAttestationRevision','ProviderCapacitySigningPermitRevision')),
 asset_id text COLLATE "C" NOT NULL,revision text COLLATE "C" NOT NULL CHECK(revision ~ '^[1-9][0-9]*$' AND length(revision)<=4300),
 identity_hash text NOT NULL CHECK(identity_hash ~ '^[0-9a-f]{64}$'),
 raw_body bytea NOT NULL CHECK(octet_length(raw_body) BETWEEN 1 AND 2097152),
 signature bytea NOT NULL CHECK(octet_length(signature)=64),
 origin_hash text NOT NULL,origin_epoch bigint NOT NULL CHECK(origin_epoch=1),
 snapshot_hash text NOT NULL,root_ordinal integer NOT NULL,
 CHECK(content_hash=encode(pg_catalog.sha256(raw_body),'hex')),
 -- NUL cannot occur in PostgreSQL text; separators bind the complete identity.
 -- Do not index full 4300-digit revision text in an oversized B-tree tuple.
 CHECK(identity_hash=encode(pg_catalog.sha256(pg_catalog.convert_to('aos-capacity-document-identity/v1','UTF8')
   ||pg_catalog.decode('00','hex')||pg_catalog.convert_to(kind,'UTF8')
   ||pg_catalog.decode('00','hex')||pg_catalog.convert_to(asset_id,'UTF8')
   ||pg_catalog.decode('00','hex')||pg_catalog.convert_to(revision,'UTF8')),'hex')),
 PRIMARY KEY(org_id,project_id,content_hash),UNIQUE(org_id,project_id,identity_hash),
 FOREIGN KEY(org_id,project_id,origin_hash) REFERENCES aos_capacity_publication_private.origin,
 FOREIGN KEY(org_id,project_id,snapshot_hash,root_ordinal) REFERENCES aos_capacity_publication_private.root_entry);

CREATE FUNCTION aos_capacity_publication_private.register_document(p_kind text,p_body bytea,p_signature bytea)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE
 fence aos_capacity_publication_private.registry_epoch%ROWTYPE;
 origin aos_capacity_publication_private.origin%ROWTYPE;
 anchor aos_capacity_publication_private.deployment_anchor%ROWTYPE;
 root aos_capacity_publication_private.root_entry%ROWTYPE;
 previous aos_capacity_publication_private.document%ROWTYPE;
 bootstrap jsonb;
 doc jsonb;
 observed_oid oid;
 observed_cluster text;
 digest text;
 identity_id text;
 publisher_points integer[];
 key_points integer[];
BEGIN
 IF session_user<>'aos_provider_capacity_policy_publisher'
   OR current_user<>'aos_capacity_publication_owner'
   OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
   OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
   OR p_signature IS NULL OR octet_length(p_signature)<>64 THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND
   (rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
   OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=session_user::regrole OR member=session_user::regrole) THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 CASE p_kind
 WHEN 'ProviderCapacitySourcePolicyRevision' THEN doc := aos_capacity_publication_private.read_source_policy(p_body);
 WHEN 'SupplierCapacityAttestationRevision' THEN doc := aos_capacity_publication_private.read_supplier_attestation(p_body);
 WHEN 'ProviderCapacitySigningPermitRevision' THEN doc := aos_capacity_publication_private.read_signing_permit(p_body);
 ELSE RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END CASE;
 IF doc IS NULL THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 digest := encode(sha256(p_body),'hex');
 identity_id := encode(sha256(convert_to('aos-capacity-document-identity/v1','UTF8')
   ||decode('00','hex')||convert_to(p_kind,'UTF8')||decode('00','hex')||convert_to(doc->>'assetId','UTF8')
   ||decode('00','hex')||convert_to(doc->>'revision','UTF8')),'hex');
 SELECT * INTO fence FROM aos_capacity_publication_private.registry_epoch
   WHERE org_id='org-org' AND project_id='dev-project' FOR UPDATE;
 IF NOT FOUND OR fence.epoch<>1 OR fence.head_origin_hash IS NULL THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 SELECT * INTO origin FROM aos_capacity_publication_private.origin
   WHERE org_id='org-org' AND project_id='dev-project' AND content_hash=fence.head_origin_hash;
 IF NOT FOUND THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 SELECT * INTO anchor FROM aos_capacity_publication_private.deployment_anchor
   WHERE org_id='org-org' AND project_id='dev-project' AND anchor_revision=fence.anchor_revision;
 IF NOT FOUND OR origin.anchor_revision<>anchor.anchor_revision THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 bootstrap := aos_capacity_publication_private.read_origin_bootstrap(origin.raw_body);
 SELECT oid INTO observed_oid FROM pg_database WHERE datname=current_database();
 SELECT system_identifier::text INTO observed_cluster FROM pg_control_system();
 IF origin.content_hash<>encode(sha256(origin.raw_body),'hex')
   OR bootstrap->>'anchorRevision' IS DISTINCT FROM anchor.anchor_revision
   OR bootstrap->>'publisher' IS DISTINCT FROM anchor.signer_publisher
   OR bootstrap->>'keyId' IS DISTINCT FROM anchor.signer_key_id
   OR bootstrap->>'publisherSubject' IS DISTINCT FROM anchor.publisher_subject
   OR bootstrap->>'rootSnapshotHash' IS DISTINCT FROM origin.snapshot_hash
   OR bootstrap->'deploymentTarget' IS DISTINCT FROM anchor.deployment_target
   OR anchor.deployment_target->>'database' IS DISTINCT FROM current_database()
   OR (anchor.deployment_target->>'databaseOid')::numeric IS DISTINCT FROM observed_oid::text::numeric
   OR anchor.deployment_target->>'clusterIdentifier' IS DISTINCT FROM observed_cluster
   OR clock_timestamp()<aos_capacity_publication_private.read_signed_time(bootstrap->'validFrom')
   OR clock_timestamp()>=aos_capacity_publication_private.read_signed_time(bootstrap->'validUntil')
   OR clock_timestamp()<aos_capacity_publication_private.read_signed_time(doc->'validFrom')
   OR clock_timestamp()>=aos_capacity_publication_private.read_signed_time(doc->'validUntil') THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 IF p_kind IN ('ProviderCapacitySourcePolicyRevision','ProviderCapacitySigningPermitRevision')
   AND doc->'deploymentTarget' IS DISTINCT FROM anchor.deployment_target THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(bootstrap->'allowedDocumentRefs') r
   WHERE r.value=jsonb_build_object('assetType',p_kind,'assetId',doc->>'assetId','revision',doc->'revision','contentHash',digest)) THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   JOIN pg_language l ON l.oid=p.prolang JOIN pg_roles r ON r.oid=p.proowner
   WHERE n.nspname='aos_ed25519' AND p.proname='verify'
     AND p.proargtypes='17 17 17'::oidvector AND p.prorettype='boolean'::regtype
     AND p.probin='$libdir/aos_ed25519' AND p.prosrc='aos_ed25519_verify'
     AND l.lanname='c' AND NOT p.prosecdef AND p.provolatile='i' AND p.proisstrict
     AND r.rolname='aos_ed25519_owner' AND n.nspowner=r.oid
     AND NOT (r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
     AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid)) THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_VERIFIER_REQUIRED' USING ERRCODE='42501';
 END IF;
 IF aos_ed25519.verify(origin.signature,origin.raw_body,anchor.signer_public_key) IS DISTINCT FROM true THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 publisher_points := ARRAY(SELECT ascii(substr(doc->>'publisher',i,1)) FROM generate_series(1,length(doc->>'publisher')) i);
 key_points := ARRAY(SELECT ascii(substr(doc->>'keyId',i,1)) FROM generate_series(1,length(doc->>'keyId')) i);
 SELECT * INTO root FROM aos_capacity_publication_private.root_entry
   WHERE org_id='org-org' AND project_id='dev-project' AND snapshot_hash=origin.snapshot_hash
     AND publisher_codepoints=publisher_points AND key_id_codepoints=key_points;
 IF NOT FOUND OR clock_timestamp()<root.not_before OR clock_timestamp()>=root.not_after
   OR (root.revoked_at IS NOT NULL AND clock_timestamp()>=root.revoked_at) THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 IF aos_ed25519.verify(p_signature,p_body,root.public_key) IS DISTINCT FROM true THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 SELECT * INTO previous FROM aos_capacity_publication_private.document
   WHERE org_id='org-org' AND project_id='dev-project' AND content_hash=digest;
 IF FOUND THEN
   IF previous.kind IS DISTINCT FROM p_kind OR previous.asset_id IS DISTINCT FROM doc->>'assetId'
     OR previous.revision IS DISTINCT FROM doc->>'revision' OR previous.raw_body IS DISTINCT FROM p_body
     OR previous.signature IS DISTINCT FROM p_signature OR previous.origin_hash IS DISTINCT FROM origin.content_hash
     OR previous.origin_epoch IS DISTINCT FROM fence.epoch OR previous.snapshot_hash IS DISTINCT FROM root.snapshot_hash
     OR previous.root_ordinal IS DISTINCT FROM root.root_ordinal THEN
     RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
   END IF;
 ELSE
   INSERT INTO aos_capacity_publication_private.document VALUES('org-org','dev-project',digest,p_kind,
     doc->>'assetId',doc->>'revision',identity_id,p_body,p_signature,origin.content_hash,fence.epoch,root.snapshot_hash,root.root_ordinal);
 END IF;
 -- Return-time validity is deliberately not claimed as final caller-COMMIT TTL.
 IF clock_timestamp()>=aos_capacity_publication_private.read_signed_time(doc->'validUntil')
   OR clock_timestamp()>=aos_capacity_publication_private.read_signed_time(bootstrap->'validUntil')
   OR clock_timestamp()>=root.not_after OR (root.revoked_at IS NOT NULL AND clock_timestamp()>=root.revoked_at) THEN
   RAISE EXCEPTION 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 RETURN digest;
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.register_document(text,bytea,bytea) FROM PUBLIC;
"""


def install_document_registry(execute):
    """Add only an empty private table and a publisher entry; no trusted seed."""
    for ddl in (CAPACITY_SOURCE_POLICY_PROFILE_SQL, CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL, DOCUMENT_SQL):
        execute(ddl)
    execute(f'ALTER TABLE {SCHEMA}.document OWNER TO {OWNER}')
    execute(f'REVOKE ALL ON TABLE {SCHEMA}.document FROM PUBLIC,{PUBLISHER},aos_runtime,aos_provider_capacity_issuer')
    execute(f'ALTER TABLE {SCHEMA}.document ENABLE ROW LEVEL SECURITY')
    execute(f'ALTER TABLE {SCHEMA}.document FORCE ROW LEVEL SECURITY')
    execute(f"CREATE POLICY owner_scope ON {SCHEMA}.document TO {OWNER} USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')) WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))")
    execute(f'CREATE TRIGGER immutable_document BEFORE UPDATE OR DELETE ON {SCHEMA}.document FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.immutable_registry_row()')
    for signature in ('read_source_policy(bytea)', 'read_supplier_attestation(bytea)', 'register_document(text,bytea,bytea)'):
        execute(f'ALTER FUNCTION {SCHEMA}.{signature} OWNER TO {OWNER}')
        execute(f'REVOKE ALL ON FUNCTION {SCHEMA}.{signature} FROM PUBLIC,{PUBLISHER},aos_runtime,aos_provider_capacity_issuer')
    execute(f'GRANT EXECUTE ON FUNCTION {SCHEMA}.register_document(text,bytea,bytea) TO {PUBLISHER}')
