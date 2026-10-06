"""Independent signed authority invalidation; no deletion, rotation or execution grant."""
from aos_api.aip_provider_capacity_publication_registry import OWNER, PUBLISHER, SCHEMA

WITHDRAWAL_TABLES = ('origin_withdrawal',)

WITHDRAWAL_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_origin_withdrawal(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE doc jsonb; ref jsonb; field text; starts_at timestamptz; ends_at timestamptz;
BEGIN
 doc := aos_capacity_publication_private.read_signed_body(p_raw);
 IF doc IS NULL OR jsonb_typeof(doc) IS DISTINCT FROM 'object'
   OR NOT (doc ?& ARRAY['schemaVersion','tenant','assetId','revision','publisher','keyId',
    'validFrom','validUntil','deploymentTarget','purpose','anchorRevision','publisherSubject',
    'policyPublisherRole','originRef','expectedEpoch'])
   OR (SELECT count(*) FROM jsonb_object_keys(doc))<>15
   OR doc->'schemaVersion' IS DISTINCT FROM '1'::jsonb
   OR doc->'tenant' IS DISTINCT FROM '{"orgId":"org-org","projectId":"dev-project"}'::jsonb
   OR doc->'purpose' IS DISTINCT FROM '"provider_capacity_origin_withdrawal"'::jsonb
   OR doc->'policyPublisherRole' IS DISTINCT FROM '"aos_provider_capacity_policy_publisher"'::jsonb
   OR jsonb_typeof(doc->'revision') IS DISTINCT FROM 'number'
   OR (doc->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$' OR length(doc->>'revision')>4300
   OR jsonb_typeof(doc->'anchorRevision') IS DISTINCT FROM 'string'
   OR (doc->>'anchorRevision') COLLATE "C" !~ '^sha256:[0-9a-f]{64}$'
   OR jsonb_typeof(doc->'expectedEpoch') IS DISTINCT FROM 'number'
   OR (doc->>'expectedEpoch') COLLATE "C" !~ '^[1-9][0-9]*$'
   OR length(doc->>'expectedEpoch')>19 OR (doc->>'expectedEpoch')::numeric>9223372036854775806 THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_REQUIRED' USING ERRCODE='22023';
 END IF;
 FOREACH field IN ARRAY ARRAY['assetId','publisher','keyId','publisherSubject'] LOOP
   PERFORM aos_capacity_publication_private.read_identifier(doc->field);
 END LOOP;
 PERFORM aos_capacity_publication_private.read_deployment_target(convert_to(
   aos_capacity_publication_private.canonical_signed_json((doc->'deploymentTarget')::json,1),'UTF8'));
 ref := doc->'originRef';
 IF jsonb_typeof(ref) IS DISTINCT FROM 'object'
   OR NOT (ref ?& ARRAY['assetType','assetId','revision','contentHash'])
   OR (SELECT count(*) FROM jsonb_object_keys(ref))<>4
   OR ref->'assetType' IS DISTINCT FROM '"ProviderCapacityOriginBootstrapRevision"'::jsonb
   OR jsonb_typeof(ref->'revision') IS DISTINCT FROM 'number'
   OR (ref->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$' OR length(ref->>'revision')>4300
   OR jsonb_typeof(ref->'contentHash') IS DISTINCT FROM 'string'
   OR (ref->>'contentHash') COLLATE "C" !~ '^[0-9a-f]{64}$' THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_REQUIRED' USING ERRCODE='22023';
 END IF;
 PERFORM aos_capacity_publication_private.read_identifier(ref->'assetId');
 starts_at := aos_capacity_publication_private.read_signed_time(doc->'validFrom');
 ends_at := aos_capacity_publication_private.read_signed_time(doc->'validUntil');
 IF starts_at>=ends_at OR extract(epoch FROM ends_at-starts_at)>31622400 THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_REQUIRED' USING ERRCODE='22023';
 END IF;
 RETURN doc;
EXCEPTION WHEN OTHERS THEN
 RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_REQUIRED' USING ERRCODE='22023';
END $body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_origin_withdrawal(bytea) FROM PUBLIC;
"""

WITHDRAWAL_SQL = r"""
CREATE TABLE aos_capacity_publication_private.origin_withdrawal(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 raw_body bytea NOT NULL CHECK(octet_length(raw_body) BETWEEN 1 AND 2097152),
 signature bytea NOT NULL CHECK(octet_length(signature)=64),
 asset_id text COLLATE "C" NOT NULL,revision text COLLATE "C" NOT NULL CHECK(revision ~ '^[1-9][0-9]*$' AND length(revision)<=4300),
 identity_hash text NOT NULL CHECK(identity_hash ~ '^[0-9a-f]{64}$'),
 origin_hash text NOT NULL,prior_epoch bigint NOT NULL CHECK(prior_epoch BETWEEN 1 AND 9223372036854775806),
 new_epoch bigint NOT NULL CHECK(new_epoch=prior_epoch+1),
 CHECK(content_hash=encode(sha256(raw_body),'hex')),
 CHECK(identity_hash=encode(sha256(convert_to('aos-capacity-origin-withdrawal-identity/v1','UTF8')
   ||decode('00','hex')||convert_to(asset_id,'UTF8')||decode('00','hex')||convert_to(revision,'UTF8')),'hex')),
 PRIMARY KEY(org_id,project_id,content_hash),UNIQUE(org_id,project_id,identity_hash),
 UNIQUE(org_id,project_id,origin_hash,prior_epoch),
 FOREIGN KEY(org_id,project_id,origin_hash) REFERENCES aos_capacity_publication_private.origin);

CREATE FUNCTION aos_capacity_publication_private.withdraw_origin(p_body bytea,p_signature bytea)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE
 doc jsonb; bootstrap jsonb; digest text;
 fence aos_capacity_publication_private.registry_epoch%ROWTYPE;
 origin aos_capacity_publication_private.origin%ROWTYPE;
 anchor aos_capacity_publication_private.deployment_anchor%ROWTYPE;
 previous aos_capacity_publication_private.origin_withdrawal%ROWTYPE;
 observed_oid oid; observed_cluster text;
BEGIN
 IF session_user<>'aos_provider_capacity_policy_publisher' OR current_user<>'aos_capacity_publication_owner'
   OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
   OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
   OR p_signature IS NULL OR octet_length(p_signature)<>64
   OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND
     (rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
   OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=session_user::regrole OR member=session_user::regrole) THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501';
 END IF;
 doc := aos_capacity_publication_private.read_origin_withdrawal(p_body);
 digest := encode(sha256(p_body),'hex');
 SELECT * INTO fence FROM aos_capacity_publication_private.registry_epoch
   WHERE org_id='org-org' AND project_id='dev-project' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501'; END IF;
 SELECT * INTO origin FROM aos_capacity_publication_private.origin
   WHERE org_id='org-org' AND project_id='dev-project' AND content_hash=doc->'originRef'->>'contentHash';
 IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501'; END IF;
 SELECT * INTO anchor FROM aos_capacity_publication_private.deployment_anchor
   WHERE org_id='org-org' AND project_id='dev-project' AND anchor_revision=fence.anchor_revision;
 IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501'; END IF;
 bootstrap := aos_capacity_publication_private.read_origin_bootstrap(origin.raw_body);
 SELECT oid INTO observed_oid FROM pg_database WHERE datname=current_database();
 SELECT system_identifier::text INTO observed_cluster FROM pg_control_system();
 IF origin.content_hash<>encode(sha256(origin.raw_body),'hex')
   OR origin.anchor_revision IS DISTINCT FROM anchor.anchor_revision
   OR bootstrap->>'anchorRevision' IS DISTINCT FROM anchor.anchor_revision
   OR bootstrap->>'publisher' IS DISTINCT FROM anchor.signer_publisher
   OR bootstrap->>'keyId' IS DISTINCT FROM anchor.signer_key_id
   OR bootstrap->>'publisherSubject' IS DISTINCT FROM anchor.publisher_subject
   OR bootstrap->'deploymentTarget' IS DISTINCT FROM anchor.deployment_target
   OR bootstrap->>'rootSnapshotHash' IS DISTINCT FROM origin.snapshot_hash
   OR doc->>'anchorRevision' IS DISTINCT FROM anchor.anchor_revision
   OR doc->>'publisher' IS DISTINCT FROM anchor.signer_publisher
   OR doc->>'keyId' IS DISTINCT FROM anchor.signer_key_id
   OR doc->>'publisherSubject' IS DISTINCT FROM anchor.publisher_subject
   OR doc->'deploymentTarget' IS DISTINCT FROM anchor.deployment_target
   OR anchor.deployment_target->>'database' IS DISTINCT FROM current_database()
   OR (anchor.deployment_target->>'databaseOid')::numeric IS DISTINCT FROM observed_oid::text::numeric
   OR anchor.deployment_target->>'clusterIdentifier' IS DISTINCT FROM observed_cluster
   OR doc->'originRef' IS DISTINCT FROM jsonb_build_object('assetType','ProviderCapacityOriginBootstrapRevision',
     'assetId',bootstrap->>'assetId','revision',bootstrap->'revision','contentHash',origin.content_hash)
   OR clock_timestamp()<aos_capacity_publication_private.read_signed_time(doc->'validFrom')
   OR clock_timestamp()>=aos_capacity_publication_private.read_signed_time(doc->'validUntil') THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   JOIN pg_language l ON l.oid=p.prolang JOIN pg_roles r ON r.oid=p.proowner
   WHERE n.nspname='aos_ed25519' AND p.proname='verify' AND p.proargtypes='17 17 17'::oidvector
     AND p.prorettype='boolean'::regtype AND p.probin='$libdir/aos_ed25519' AND p.prosrc='aos_ed25519_verify'
     AND l.lanname='c' AND NOT p.prosecdef AND p.provolatile='i' AND p.proisstrict
     AND r.rolname='aos_ed25519_owner' AND n.nspowner=r.oid
     AND NOT (r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
     AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid)) THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_VERIFIER_REQUIRED' USING ERRCODE='42501';
 END IF;
 IF aos_ed25519.verify(origin.signature,origin.raw_body,anchor.signer_public_key) IS DISTINCT FROM true
   OR aos_ed25519.verify(p_signature,p_body,anchor.signer_public_key) IS DISTINCT FROM true THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501';
 END IF;
 SELECT * INTO previous FROM aos_capacity_publication_private.origin_withdrawal
   WHERE org_id='org-org' AND project_id='dev-project' AND content_hash=digest;
 IF FOUND THEN
   IF previous.raw_body IS DISTINCT FROM p_body OR previous.signature IS DISTINCT FROM p_signature
     OR previous.asset_id IS DISTINCT FROM doc->>'assetId' OR previous.revision IS DISTINCT FROM doc->>'revision'
     OR previous.origin_hash IS DISTINCT FROM origin.content_hash
     OR previous.prior_epoch IS DISTINCT FROM (doc->>'expectedEpoch')::bigint
     OR fence.epoch IS DISTINCT FROM previous.new_epoch OR fence.head_origin_hash IS NOT NULL THEN
     RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501';
   END IF;
 ELSE
   IF fence.epoch IS DISTINCT FROM (doc->>'expectedEpoch')::bigint
     OR fence.head_origin_hash IS DISTINCT FROM origin.content_hash THEN
     RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501';
   END IF;
   INSERT INTO aos_capacity_publication_private.origin_withdrawal VALUES('org-org','dev-project',digest,p_body,p_signature,
     doc->>'assetId',doc->>'revision',encode(sha256(convert_to('aos-capacity-origin-withdrawal-identity/v1','UTF8')
       ||decode('00','hex')||convert_to(doc->>'assetId','UTF8')||decode('00','hex')||convert_to(doc->>'revision','UTF8')),'hex'),
     origin.content_hash,fence.epoch,fence.epoch+1);
   UPDATE aos_capacity_publication_private.registry_epoch SET epoch=fence.epoch+1,head_origin_hash=NULL
     WHERE org_id='org-org' AND project_id='dev-project';
 END IF;
 -- Return-time expiry is not a final caller-COMMIT clock guarantee.
 IF clock_timestamp()>=aos_capacity_publication_private.read_signed_time(doc->'validUntil') THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' USING ERRCODE='42501';
 END IF;
 RETURN digest;
END $body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.withdraw_origin(bytea,bytea) FROM PUBLIC;
"""


def install_withdrawal_registry(execute):
    """Only the empty audit table and signed authority entrypoint are installed."""
    execute(WITHDRAWAL_PROFILE_SQL)
    execute(WITHDRAWAL_SQL)
    execute(f'ALTER TABLE {SCHEMA}.origin_withdrawal OWNER TO {OWNER}')
    execute(f'REVOKE ALL ON TABLE {SCHEMA}.origin_withdrawal FROM PUBLIC,{PUBLISHER},aos_runtime,aos_provider_capacity_issuer')
    execute(f'ALTER TABLE {SCHEMA}.origin_withdrawal ENABLE ROW LEVEL SECURITY')
    execute(f'ALTER TABLE {SCHEMA}.origin_withdrawal FORCE ROW LEVEL SECURITY')
    execute(f"CREATE POLICY owner_scope ON {SCHEMA}.origin_withdrawal TO {OWNER} USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')) WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))")
    execute(f'CREATE TRIGGER immutable_origin_withdrawal BEFORE UPDATE OR DELETE ON {SCHEMA}.origin_withdrawal FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.immutable_registry_row()')
    for signature in ('read_origin_withdrawal(bytea)', 'withdraw_origin(bytea,bytea)'):
        execute(f'ALTER FUNCTION {SCHEMA}.{signature} OWNER TO {OWNER}')
        execute(f'REVOKE ALL ON FUNCTION {SCHEMA}.{signature} FROM PUBLIC,{PUBLISHER},aos_runtime,aos_provider_capacity_issuer')
    execute(f'GRANT EXECUTE ON FUNCTION {SCHEMA}.withdraw_origin(bytea,bytea) TO {PUBLISHER}')
