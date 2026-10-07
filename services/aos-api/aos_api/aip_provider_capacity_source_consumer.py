"""Current nonexecuting Source facts through the controlled issuer service."""
CONSUMER_ENTRY=('read_current_capacity_source','p_raw bytea,p_ref jsonb',
    'asset_id text,revision integer,content_hash text,source_raw bytea,signature bytea',
    None,None,'bytea,jsonb')


class ProviderCapacityConsumptionBlocked(ValueError):
    pass


def consumer_entry_statements(guard):
    """Compile fixed SQL only; neither install nor grant production authority."""
    from aos_api.aip_provider_capacity_publication_transaction import CAPACITY_SOURCE_PENDING_SQL
    # Reuse complete construction from trusted issuance SQL, not a copy or
    # database/caller supplied field mapping.
    start=' v_doc:=jsonb_build_object('
    end=' PERFORM aos_capacity_publication_private.read_identifier(v_doc'
    if CAPACITY_SOURCE_PENDING_SQL.count(start)!=1 or CAPACITY_SOURCE_PENDING_SQL.count(end)!=1:
        raise ValueError('CAPACITY_SOURCE_DOCUMENT_COMPILER_DRIFTED')
    document=start+CAPACITY_SOURCE_PENDING_SQL.split(start)[1].split(end)[0]
    body=r"""
DECLARE
 v_ref jsonb;v_public aos_capacity_publication_private.source_publication%ROWTYPE;
 v_pending aos_capacity_publication_private.source_pending%ROWTYPE;
 v_provenance aos_capacity_publication_private.source_provenance%ROWTYPE;
 v_input jsonb;v_packet jsonb;v_historical_packet jsonb;v_facts jsonb;v_source jsonb;
 v_account jsonb;v_basis jsonb;v_permit jsonb;v_attestation jsonb;v_origin jsonb;
 v_evidence jsonb;v_context jsonb;v_doc jsonb;v_historical jsonb;
 v_account_id uuid;v_now_text text;v_now timestamptz;p_source_asset_id text;p_permit_ref jsonb;
 v_root aos_capacity_publication_private.root_entry%ROWTYPE;
BEGIN
""" + guard + r"""
 PERFORM aos_capacity_publication_private.require_current_source_installation();
 v_ref:=aos_capacity_publication_private.original_source_ref(p_ref,'ProviderCapacitySourceRevision');
 IF v_ref->'revision' IS DISTINCT FROM '1'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_REF_REQUIRED' USING ERRCODE='22023'; END IF;
 SELECT p.* INTO STRICT v_public FROM aos_capacity_publication_private.source_publication p
 WHERE p.org_id='org-org' AND p.project_id='dev-project' AND p.asset_id=v_ref->>'assetId';
 SELECT s.* INTO STRICT v_pending FROM aos_capacity_publication_private.source_pending s
 WHERE s.attempt_id=v_public.attempt_id;
 SELECT p.* INTO STRICT v_provenance FROM aos_capacity_publication_private.source_provenance p
 WHERE p.org_id='org-org' AND p.project_id='dev-project' AND p.asset_id=v_public.asset_id;
 IF NOT v_pending.finalized OR v_public.source_raw<>v_pending.source_raw
  OR v_public.content_hash<>v_ref->>'contentHash'
  OR v_public.content_hash<>encode(sha256(v_public.source_raw),'hex')
  OR v_pending.source_hash<>v_public.content_hash OR v_public.account_id<>v_pending.account_id
  OR (v_pending.org_id,v_pending.project_id,v_pending.source_asset_id)
    IS DISTINCT FROM ('org-org'::text,'dev-project'::text,v_public.asset_id)
  OR v_provenance.original_signed_facts<>v_pending.signed_facts
  OR (v_provenance.native_xid,v_provenance.native_pid,v_provenance.native_session)
    IS DISTINCT FROM (v_pending.native_xid,v_pending.native_pid,v_pending.native_session)
  OR v_pending.native_session<>'aos_provider_capacity_issuer' THEN
  RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_PROVENANCE_REQUIRED' USING ERRCODE='22023'; END IF;
 v_historical_packet:=aos_capacity_publication_private.read_signed_body(v_pending.command_raw);
 v_historical:=aos_capacity_publication_private.read_signed_body(v_public.source_raw);
 -- History is provenance; ingress independently authenticates the new packet.
 v_input:=aos_capacity_publication_private.read_source_command_signed_facts(p_raw,v_pending.permit_ref);
 IF v_input-ARRAY['packet','facts'] IS DISTINCT FROM v_pending.signed_facts-ARRAY['packet','facts']
  OR (v_input->'facts')-ARRAY['xid','pid'] IS DISTINCT FROM (v_pending.signed_facts->'facts')-ARRAY['xid','pid']
  OR v_pending.signed_facts->'facts'->>'xid' IS DISTINCT FROM v_pending.native_xid::text
  OR v_pending.signed_facts->'facts'->>'pid' IS DISTINCT FROM v_pending.native_pid::text
  OR v_historical_packet IS DISTINCT FROM v_pending.signed_facts->'packet'
  OR (v_input->'packet')-'authentication' IS DISTINCT FROM v_historical_packet-'authentication'
  OR v_input->'packet'->>'makerSubject' IS DISTINCT FROM v_pending.maker
  OR v_input->'packet'->>'requestHash' IS DISTINCT FROM v_pending.request_hash THEN
  RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_FACTS_REQUIRED' USING ERRCODE='22023'; END IF;
 v_facts:=v_input->'facts';v_account:=v_facts->'account';v_basis:=v_facts->'basis';
 -- This suffix follows the complete original/registered-material lock prefix.
 PERFORM 1 FROM aos_capacity_publication_private.global_account a
 WHERE a.account_id=v_public.account_id AND a.org_id='org-org' AND a.project_id='dev-project'
  AND a.supplier_id=v_account->>'supplierId' AND a.fingerprint=v_account->>'supplierAccountFingerprint' FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_MAPPING_REQUIRED' USING ERRCODE='22023'; END IF;
 FOR v_ref IN SELECT value FROM jsonb_array_elements(v_account->'providerRefs') ORDER BY value->>'assetId' COLLATE "C" LOOP
  PERFORM 1 FROM aos_capacity_publication_private.global_provider m WHERE m.provider_id=v_ref->>'assetId'
   AND m.account_id=v_public.account_id AND m.org_id='org-org' AND m.project_id='dev-project' FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_MAPPING_REQUIRED' USING ERRCODE='22023'; END IF;
 END LOOP;
 -- A lock wait can cross expiry; recheck original deadlines/current roots again.
 IF aos_capacity_publication_private.read_source_command_signed_facts(p_raw,v_pending.permit_ref) IS DISTINCT FROM v_input THEN
  RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_FACTS_REQUIRED' USING ERRCODE='22023'; END IF;
 v_packet:=v_historical_packet;v_source:=v_facts->'source';
 v_permit:=v_input->'signedDocuments'->'ProviderCapacitySigningPermitRevision';
 v_attestation:=v_input->'signedDocuments'->'SupplierCapacityAttestationRevision';
 SELECT aos_capacity_publication_private.read_origin_bootstrap(o.raw_body) INTO STRICT v_origin
 FROM aos_capacity_publication_private.origin o WHERE o.org_id='org-org' AND o.project_id='dev-project'
  AND o.content_hash=v_input->'origin'->>'originHash';
 SELECT jsonb_agg(e.ref ORDER BY e.ref->>'assetType' COLLATE "C",e.ref->>'assetId' COLLATE "C") INTO v_evidence
 FROM (SELECT DISTINCT value AS ref FROM jsonb_array_elements(jsonb_build_array(
  v_facts->'application'->'basisEvidenceRef',v_account->'evidenceRef',v_basis->'evidenceRef'))) e;
 v_account_id:=v_public.account_id;p_source_asset_id:=v_public.asset_id;p_permit_ref:=v_pending.permit_ref;
 v_now_text:=v_historical->>'issuedAt';
 v_context:=(v_packet->'authentication')||jsonb_build_object('issuerRole',v_pending.native_session,
  'transactionId',v_pending.native_xid::text,'backendPid',v_pending.native_pid,'attemptId',v_pending.attempt_id::text);
""" + document + r"""
 IF convert_to(aos_capacity_publication_private.canonical_signed_json(v_doc::json,1),'UTF8')<>v_public.source_raw
  OR v_provenance.source_signer_root_revision IS DISTINCT FROM v_input->>'sourceSignerRootRevision'
  OR aos_ed25519.verify(v_public.signature,v_public.source_raw,
      decode(v_input->>'sourceSignerPublicKey','base64')) IS NOT TRUE THEN
  RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_SIGNATURE_REQUIRED' USING ERRCODE='22023'; END IF;
 IF aos_capacity_publication_private.read_source_command_signed_facts(p_raw,v_pending.permit_ref) IS DISTINCT FROM v_input THEN
  RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_FACTS_REQUIRED' USING ERRCODE='22023'; END IF;
 v_now:=clock_timestamp();
 FOR v_ref IN SELECT value FROM jsonb_each(v_input->'signedDocuments') UNION ALL SELECT v_origin LOOP
  IF v_now<aos_capacity_publication_private.read_signed_time(v_ref->'validFrom')
   OR v_now>=aos_capacity_publication_private.read_signed_time(v_ref->'validUntil') THEN
   RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_EXPIRED' USING ERRCODE='22023'; END IF;
 END LOOP;
 FOR v_ref IN SELECT value FROM jsonb_each(v_input->'signedDocuments')
  UNION ALL SELECT jsonb_build_object('publisher',v_permit->'signerPublisher','keyId',v_permit->'signerKeyId') LOOP
  SELECT r.* INTO STRICT v_root FROM aos_capacity_publication_private.root_entry r
  WHERE r.org_id='org-org' AND r.project_id='dev-project' AND r.snapshot_hash=v_input->'origin'->>'snapshotHash'
   AND r.publisher_codepoints=ARRAY(SELECT ascii(substr(v_ref->>'publisher',i,1)) FROM generate_series(1,length(v_ref->>'publisher')) i)
   AND r.key_id_codepoints=ARRAY(SELECT ascii(substr(v_ref->>'keyId',i,1)) FROM generate_series(1,length(v_ref->>'keyId')) i);
  IF v_now<v_root.not_before OR v_now>=v_root.not_after
   OR (v_root.revoked_at IS NOT NULL AND v_now>=v_root.revoked_at) THEN
   RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_EXPIRED' USING ERRCODE='22023'; END IF;
 END LOOP;
 IF v_now<aos_capacity_publication_private.read_signed_time(v_historical->'validFrom')
  OR v_now>=aos_capacity_publication_private.read_signed_time(v_historical->'validUntil')
  OR v_now<aos_capacity_publication_private.read_signed_time(v_historical->'issuedAt')
  OR v_now>=aos_capacity_publication_private.read_signed_time(v_input->'packet'->'authentication'->'authenticationExpiresAt') THEN
  RAISE EXCEPTION 'CAPACITY_CURRENT_SOURCE_EXPIRED' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT v_public.asset_id,1,v_public.content_hash,v_public.source_raw,v_public.signature;
END
"""
    signature='public.read_current_capacity_source(bytea,jsonb)'
    ddl=(f'CREATE FUNCTION public.read_current_capacity_source(p_raw bytea,p_ref jsonb) '
         f'RETURNS TABLE({CONSUMER_ENTRY[2]}) LANGUAGE plpgsql VOLATILE SECURITY DEFINER '
         'SET search_path=pg_catalog AS $consumer$'+body+'$consumer$;')
    return (ddl,f'ALTER FUNCTION {signature} OWNER TO aos_capacity_publication_owner',
        f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {signature} TO aos_provider_capacity_issuer')


def read_current_capacity_source(conn,command,source_ref):
    """Revalidate current personnel and DB authority, without COMMIT or execution."""
    import hashlib
    import psycopg
    from psycopg.types.json import Jsonb
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_provider_capacity_source_issuer import capacity_source_preparation_bytes
    from aos_api.aip_provider_capacity_formal_boundary import _require_read_boundary,require_capacity_issuer_identity
    from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2,parse_signed_capacity_body
    from aos_api.tenant_scope import TenantScope
    try:
        if type(conn) is not psycopg.Connection or type(source_ref) is not FormalExactRef:
            raise ValueError('exact caller and Source required')
        ref=FormalExactRef.model_validate(source_ref.model_dump(mode='python',by_alias=True))
        if ref.asset_type!='ProviderCapacitySourceRevision' or ref.revision!=1:
            raise ValueError('published Source required')
        packet=capacity_source_preparation_bytes(command)
        require_capacity_issuer_identity(conn,TenantScope('org-org','dev-project'))
        if not conn.pgconn.used_password or conn.info.get_parameters().get('require_auth')!='scram-sha-256':
            raise ValueError('native SCRAM caller required')
        _require_read_boundary(conn)
        row=conn.execute('SELECT * FROM public.read_current_capacity_source(%s,%s::jsonb)',
            (packet,Jsonb(ref.model_dump(mode='json',by_alias=True)))).fetchone()
        if row is None or capacity_source_preparation_bytes(command)!=packet:
            raise ValueError('current identity required after waits')
        raw=bytes(row['source_raw'])
        source=parse_signed_capacity_body(raw,PublishedProviderCapacitySourceV2)
        if (row['asset_id']!=ref.asset_id or row['revision']!=ref.revision or row['content_hash']!=ref.content_hash
            or hashlib.sha256(raw).hexdigest()!=ref.content_hash or source.asset_id!=ref.asset_id
            or source.revision!=ref.revision or source.execution_allowed is not False
            or (source.tenant.org_id,source.tenant.project_id)!=('org-org','dev-project')):
            raise ValueError('exact nonexecuting Source required')
        return source
    except Exception:
        raise ProviderCapacityConsumptionBlocked('CAPACITY_CURRENT_SOURCE_REQUIRED') from None
