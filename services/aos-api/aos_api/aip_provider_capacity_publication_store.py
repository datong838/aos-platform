"""Publication SQL prerequisites; no operational publication Store yet.

These pure encoding and untrusted shape checks do not authenticate a
signature/key or grant capacity. Production installation and the
full approval/currentness/mapping/signature/COMMIT boundary remain separate.
"""

# Root file identifiers have a wider domain than signed document identifiers.
# Return codepoints rather than PostgreSQL text, which cannot hold surrogates.
# This validates syntax only; it does not establish trust or register a root.
CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_root_identifier_literal(p_literal text)
RETURNS integer[] LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  size integer := pg_catalog.length(p_literal);
  pos integer := 2;
  code integer;
  low_code integer;
  escape text;
  digits text;
  points integer[] := ARRAY[]::integer[];
  strip_points constant integer[] := ARRAY[9,10,11,12,13,28,29,30,31,32,133,160,5760,
      8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288];
BEGIN
  IF p_literal IS NULL OR size NOT BETWEEN 3 AND 2882
      OR pg_catalog.octet_length(p_literal) <> size
      OR pg_catalog.left(p_literal,1) <> '"' OR pg_catalog.right(p_literal,1) <> '"' THEN
    RAISE EXCEPTION 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
  END IF;
  WHILE pos < size LOOP
    code := pg_catalog.ascii(pg_catalog.substr(p_literal,pos,1));
    IF code = 92 THEN
      escape := pg_catalog.substr(p_literal,pos+1,1);
      IF escape = 'u' THEN
        digits := pg_catalog.substr(p_literal,pos+2,4);
        IF pos+5 >= size OR digits COLLATE "C" !~ '^[0-9a-f]{4}$' THEN
          RAISE EXCEPTION 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
        END IF;
        code := ('x'||digits)::bit(16)::integer;
        -- Canonical ensure_ascii uses literal printable ASCII and short escapes.
        IF code BETWEEN 32 AND 126 OR code = ANY(ARRAY[8,9,10,12,13]) THEN
          RAISE EXCEPTION 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
        END IF;
        pos := pos+6;
        IF code BETWEEN 55296 AND 56319 AND pos+5 < size
            AND pg_catalog.substr(p_literal,pos,2) = E'\\u' THEN
          digits := pg_catalog.substr(p_literal,pos+2,4);
          IF digits COLLATE "C" ~ '^[0-9a-f]{4}$' THEN
            low_code := ('x'||digits)::bit(16)::integer;
            IF low_code BETWEEN 56320 AND 57343 THEN
              code := 65536+(code-55296)*1024+low_code-56320;
              pos := pos+6;
            END IF;
          END IF;
        END IF;
      ELSE
        code := CASE escape WHEN '"' THEN 34 WHEN E'\\' THEN 92
          WHEN 'b' THEN 8 WHEN 't' THEN 9 WHEN 'n' THEN 10 WHEN 'f' THEN 12 WHEN 'r' THEN 13
          ELSE NULL END;
        IF code IS NULL OR pos+1 >= size THEN
          RAISE EXCEPTION 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
        END IF;
        pos := pos+2;
      END IF;
    ELSE
      IF code NOT BETWEEN 32 AND 126 OR code = 34 THEN
        RAISE EXCEPTION 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
      END IF;
      pos := pos+1;
    END IF;
    IF code = 0 OR pg_catalog.cardinality(points) >= 240 THEN
      RAISE EXCEPTION 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
    END IF;
    points := pg_catalog.array_append(points,code);
  END LOOP;
  IF pos <> size OR pg_catalog.cardinality(points) = 0
      OR points[1] = ANY(strip_points)
      OR points[pg_catalog.cardinality(points)] = ANY(strip_points) THEN
    RAISE EXCEPTION 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
  END IF;
  RETURN points;
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_root_identifier_literal(text) FROM PUBLIC;
"""

# S08 snapshot only. Full approval consumers must separately enforce original
# proposal/Owner/withdrawal locks, exact references and current non-NULL expiry.
CAPACITY_APPROVAL_EVENT_PROJECTION_SQL = r"""
WITH original AS (
  SELECT e.*,
    CASE WHEN expires_at IS NULL THEN NULL ELSE
      pg_catalog.to_char(expires_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS') ||
      CASE WHEN pg_catalog.to_char(expires_at AT TIME ZONE 'UTC','US')='000000' THEN ''
        ELSE '.' || pg_catalog.to_char(expires_at AT TIME ZONE 'UTC','US') END || 'Z' END AS expiry,
    pg_catalog.to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS') ||
      CASE WHEN pg_catalog.to_char(created_at AT TIME ZONE 'UTC','US')='000000' THEN ''
        ELSE '.' || pg_catalog.to_char(created_at AT TIME ZONE 'UTC','US') END || 'Z' AS created
  FROM public.aip_action_approval_event e
  WHERE org_id=%(org_id)s AND project_id=%(project_id)s AND approval_event_id=%(approval_event_id)s
    AND org_id='org-org' AND project_id='dev-project'
    AND pg_catalog.current_setting('TimeZone')='UTC' AND proposal_version >= 1
    AND pg_catalog.isfinite(created_at) AND extract(year FROM created_at AT TIME ZONE 'UTC') BETWEEN 1 AND 9999
    AND (expires_at IS NULL OR (pg_catalog.isfinite(expires_at)
      AND extract(year FROM expires_at AT TIME ZONE 'UTC') BETWEEN 1 AND 9999))
    AND (action_binding_hash IS NULL OR action_binding_hash COLLATE pg_catalog."C" ~ '^[0-9a-f]{64}$')
    AND (approval_policy_hash IS NULL OR approval_policy_hash COLLATE pg_catalog."C" ~ '^[0-9a-f]{64}$')
    AND (eligibility_snapshot_hash IS NULL OR eligibility_snapshot_hash COLLATE pg_catalog."C" ~ '^[0-9a-f]{64}$')
), body AS (
  SELECT proposal_id,pg_catalog.jsonb_build_object(
    'id',approval_event_id,'proposalId',proposal_id,'proposalVersion',proposal_version,
    'proposalHash',proposal_hash,'decision',decision,
    'actor',pg_catalog.jsonb_build_object('actorType','user','actorId',actor_id),'reason',reason,
    'expiresAt',expiry,'createdAt',created,'actionBindingHash',action_binding_hash,
    'approvalPolicyHash',approval_policy_hash,'slotId',slot_id,
    'eligibilitySnapshotHash',eligibility_snapshot_hash) AS value
  FROM original
), encoded AS (
  SELECT proposal_id,value,public.canonical_asset_registry_jsonb(value) AS canonical FROM body
)
SELECT proposal_id,value,canonical,
  pg_catalog.encode(public.digest(pg_catalog.convert_to(canonical,'UTF8'),'sha256'),'hex') AS hash FROM encoded
"""

# S11 immutable storage fence, used by the original guard. A returned row is
# still unverified application data: typed terms/current dependencies follow.
CAPACITY_REQUEST_ROW_SQL = r"""
WITH actual AS (
  SELECT r.*,pg_catalog.encode(public.digest(pg_catalog.convert_to(
    public.canonical_asset_registry_jsonb(request_json),'UTF8'),'sha256'),'hex') AS actual_hash
  FROM public.aip_provider_capacity_request r
  WHERE org_id=%(org_id)s AND project_id=%(project_id)s AND request_id=%(request_id)s
    AND org_id='org-org' AND project_id='dev-project'
)
SELECT * FROM actual
WHERE request_hash=%(request_hash)s AND actual_hash=%(request_hash)s
  AND authorization_mode='REQUEST_ONLY_NO_CAPACITY_NO_START'
  AND basis_verified IS FALSE AND execution_allowed IS FALSE
  AND expires_at > pg_catalog.clock_timestamp()
  AND CASE WHEN pg_catalog.jsonb_typeof(request_json)='object' THEN
    request_json ?& ARRAY['application','makerSubject']
    AND (SELECT count(*) FROM pg_catalog.jsonb_object_keys(request_json))=2
    ELSE FALSE END
  AND pg_catalog.jsonb_typeof(request_json->'makerSubject')='string'
  AND request_json->>'makerSubject'=created_by
"""

# S12 original candidate storage fence. Returned data remains an unverified
# claim; original typed models and Provider/Evidence dependencies follow.
CAPACITY_CANDIDATE_ROW_SQL = r"""
WITH actual AS (
  SELECT c.*,pg_catalog.encode(public.digest(pg_catalog.convert_to(
    public.canonical_asset_registry_jsonb(request_json),'UTF8'),'sha256'),'hex') AS actual_hash
  FROM public.aip_provider_capacity_candidate c
  WHERE org_id=%(org_id)s AND project_id=%(project_id)s AND candidate_id=%(candidate_id)s
    AND revision=%(revision)s AND candidate_kind=%(candidate_kind)s
    AND org_id='org-org' AND project_id='dev-project'
)
SELECT * FROM actual
WHERE content_hash=%(content_hash)s AND actual_hash=%(content_hash)s
  AND authorization_mode='CANDIDATE_ONLY_NO_CAPACITY_NO_START'
  AND basis_verified IS FALSE AND execution_allowed IS FALSE
  AND created_by=%(maker)s
  AND CASE WHEN pg_catalog.jsonb_typeof(request_json)='object' THEN
    request_json ?& ARRAY['candidateKind','candidate','makerSubject']
    AND (SELECT count(*) FROM pg_catalog.jsonb_object_keys(request_json))=3
    ELSE FALSE END
  AND pg_catalog.jsonb_typeof(request_json->'candidateKind')='string'
  AND request_json->>'candidateKind'=candidate_kind
  AND pg_catalog.jsonb_typeof(request_json->'makerSubject')='string'
  AND request_json->>'makerSubject'=created_by
"""


def _combination_candidate_sql(kind, *, statement=CAPACITY_CANDIDATE_ROW_SQL):
    # Only the two fixed original kinds are used, never caller SQL or names.
    statement=statement.replace('%(candidate_kind)s',"'"+kind+"'")
    for field in ('candidate_id','revision','content_hash'):
        target={'candidate_id':'id','revision':'revision','content_hash':'hash'}[field]
        statement=statement.replace('%('+field+')s','%('+kind+'_'+target+')s')
    return statement


def _original_exact_ref_sql(value):
    # Fixed internal expressions only. Mirror original populate_by_name for
    # the three aliased fields without dropping unknown or duplicate fields.
    value='('+value+')'
    return f"""CASE WHEN pg_catalog.jsonb_typeof({value})='object' THEN
      CASE WHEN (SELECT count(*) FROM pg_catalog.jsonb_object_keys({value}))=4
        AND {value} - ARRAY['assetType','asset_type','assetId','asset_id','revision','contentHash','content_hash']='{{}}'::jsonb
        AND (({value} ? 'assetType') <> ({value} ? 'asset_type'))
        AND (({value} ? 'assetId') <> ({value} ? 'asset_id'))
        AND (({value} ? 'contentHash') <> ({value} ? 'content_hash'))
        AND {value} ? 'revision'
      THEN pg_catalog.jsonb_build_object(
        'assetType',COALESCE({value}->'assetType',{value}->'asset_type'),
        'assetId',COALESCE({value}->'assetId',{value}->'asset_id'),
        'revision',{value}->'revision',
        'contentHash',COALESCE({value}->'contentHash',{value}->'content_hash'))
      ELSE NULL END ELSE NULL END"""


# Original S13 combination, reading all three authoritative stored claims.
# This does not replace typed models, original approvals or dependency locks.
CAPACITY_SOURCE_COMBINATION_SQL = (
    'WITH request AS ('+CAPACITY_REQUEST_ROW_SQL+'), account AS ('+
    _combination_candidate_sql('account')+'), basis AS ('+
    _combination_candidate_sql('basis')+f"""), terms AS (
      SELECT a.candidate_id,a.revision,a.content_hash,
        a.request_json->'candidate' AS account,
        b.request_json->'candidate' AS basis,
        r.request_json->'application' AS application
      FROM account a CROSS JOIN basis b CROSS JOIN request r
      WHERE r.created_by=%(maker)s
    ) SELECT 1 AS matched FROM terms
    WHERE {_original_exact_ref_sql("basis->'physicalAccountRef'")}=pg_catalog.jsonb_build_object(
      'assetType','ProviderPhysicalAccountCandidateRevision','assetId',candidate_id,
      'revision',revision,'contentHash',content_hash)
      AND pg_catalog.jsonb_typeof(account->'physicalAccountId')='string'
      AND pg_catalog.jsonb_typeof(application->'physicalAccountId')='string'
      AND account->'physicalAccountId'=application->'physicalAccountId'
      AND CASE WHEN pg_catalog.jsonb_typeof(account->'providerRefs')='array' THEN
        EXISTS(SELECT 1 FROM pg_catalog.jsonb_array_elements(account->'providerRefs') AS refs(value)
               WHERE {_original_exact_ref_sql('value')}=application->'providerRef') ELSE FALSE END
      AND CASE WHEN pg_catalog.jsonb_typeof(basis->'maxConcurrency')='number'
        AND pg_catalog.jsonb_typeof(application->'requestedMaxConcurrency')='number'
        AND pg_catalog.length(basis->>'maxConcurrency')<=7
        AND pg_catalog.length(application->>'requestedMaxConcurrency')<=7
        AND (basis->>'maxConcurrency') COLLATE pg_catalog."C" ~ '^[1-9][0-9]*$'
        AND (application->>'requestedMaxConcurrency') COLLATE pg_catalog."C" ~ '^[1-9][0-9]*$'
      THEN (basis->>'maxConcurrency')::integer BETWEEN 1 AND 1000000
        AND (application->>'requestedMaxConcurrency')::integer BETWEEN 1 AND 1000000
        AND (basis->>'maxConcurrency')::integer <= (application->>'requestedMaxConcurrency')::integer
      ELSE FALSE END
""")

CAPACITY_SIGNED_BODY_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.canonical_signed_json(p_value json, p_depth integer)
RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  kind text;
  rendered text;
  total integer;
  unique_keys integer;
BEGIN
  kind := pg_catalog.json_typeof(p_value);
  IF p_depth < 1 OR (kind IN ('object','array') AND p_depth > 32) THEN
    RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_DEPTH' USING ERRCODE='22023';
  END IF;
  IF kind='object' THEN
    SELECT count(*), count(DISTINCT key COLLATE "C") INTO total,unique_keys
      FROM pg_catalog.json_each(p_value);
    IF total>1000 THEN
      RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_OBJECT' USING ERRCODE='22023';
    END IF;
    IF total <> unique_keys THEN
      RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_DUPLICATE_KEY' USING ERRCODE='22023';
    END IF;
    SELECT '{' || COALESCE(pg_catalog.string_agg(pg_catalog.to_json(key)::text || ':' ||
      aos_capacity_publication_private.canonical_signed_json(value,p_depth+1),
      ',' ORDER BY key COLLATE "C"),'') || '}' INTO rendered FROM pg_catalog.json_each(p_value);
    RETURN rendered;
  ELSIF kind='array' THEN
    IF pg_catalog.json_array_length(p_value)>1000 THEN
      RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_ARRAY' USING ERRCODE='22023';
    END IF;
    SELECT '[' || COALESCE(pg_catalog.string_agg(
      aos_capacity_publication_private.canonical_signed_json(value,p_depth+1),
      ',' ORDER BY ordinal),'') || ']' INTO rendered
      FROM pg_catalog.json_array_elements(p_value) WITH ORDINALITY AS entries(value,ordinal);
    RETURN rendered;
  ELSIF kind='string' THEN
    RETURN pg_catalog.to_json(p_value #>> ARRAY[]::text[])::text;
  ELSIF kind='number' THEN
    rendered := p_value::text;
    IF rendered !~ '^(0|-?[1-9][0-9]*)$' THEN
      RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_NON_INTEGER' USING ERRCODE='22023';
    END IF;
    RETURN rendered;
  ELSIF kind IN ('boolean','null') THEN
    RETURN p_value::text;
  END IF;
  RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_TYPE' USING ERRCODE='22023';
END
$body$;

CREATE FUNCTION aos_capacity_publication_private.read_signed_body(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  parsed json;
  rendered text;
BEGIN
  IF pg_catalog.current_setting('server_encoding') <> 'UTF8' THEN
    RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_ENCODING' USING ERRCODE='22023';
  END IF;
  IF pg_catalog.octet_length(p_raw)<1 OR pg_catalog.octet_length(p_raw)>2097152 THEN
    RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_SIZE' USING ERRCODE='22023';
  END IF;
  parsed := pg_catalog.convert_from(p_raw,'UTF8')::json;
  rendered := aos_capacity_publication_private.canonical_signed_json(parsed,1);
  IF pg_catalog.convert_to(rendered,'UTF8') <> p_raw THEN
    RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_NONCANONICAL' USING ERRCODE='22023';
  END IF;
  RETURN parsed::jsonb;
EXCEPTION WHEN OTHERS THEN
  -- Invalid UTF8/JSON/NUL and other parser failures must never echo body bytes.
  RAISE EXCEPTION 'CAPACITY_SIGNED_BODY_PROFILE_REQUIRED' USING ERRCODE='22023';
END
$body$;

REVOKE ALL ON SCHEMA aos_capacity_publication_private FROM PUBLIC;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.canonical_signed_json(json,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_signed_body(bytea) FROM PUBLIC;
"""

# Structure only: the full entry must independently bind this exact target to
# its trusted installation and native database/cluster, never caller claims.
CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_deployment_target(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  p_target jsonb;
  field text;
  value text;
  upper_bound numeric;
BEGIN
  p_target := aos_capacity_publication_private.read_signed_body(p_raw);
  IF p_target IS NULL OR pg_catalog.jsonb_typeof(p_target) IS DISTINCT FROM 'object' THEN
    RAISE EXCEPTION 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF NOT (p_target ?& ARRAY['host','port','database','databaseOid','clusterIdentifier','issuerRole'])
      OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(p_target)) <> 6 THEN
    RAISE EXCEPTION 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOREACH field IN ARRAY ARRAY['host','database','clusterIdentifier','issuerRole'] LOOP
    IF pg_catalog.jsonb_typeof(p_target->field) IS DISTINCT FROM 'string' THEN
      RAISE EXCEPTION 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' USING ERRCODE='22023';
    END IF;
  END LOOP;
  IF p_target->>'host' NOT IN ('127.0.0.1','::1')
      OR p_target->>'issuerRole' <> 'aos_provider_capacity_issuer'
      OR (p_target->>'database') COLLATE "C" !~ '^[a-z][a-z0-9_]{0,62}$'
      OR (p_target->>'clusterIdentifier') COLLATE "C" !~ '^[0-9]{10,20}$' THEN
    RAISE EXCEPTION 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOREACH field IN ARRAY ARRAY['port','databaseOid'] LOOP
    value := p_target->>field;
    IF pg_catalog.jsonb_typeof(p_target->field) IS DISTINCT FROM 'number'
        OR value !~ '^[1-9][0-9]*$' THEN
      RAISE EXCEPTION 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' USING ERRCODE='22023';
    END IF;
    upper_bound := CASE WHEN field='port' THEN 65535 ELSE 4294967295 END;
    IF value::numeric > upper_bound THEN
      RAISE EXCEPTION 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' USING ERRCODE='22023';
    END IF;
  END LOOP;
  RETURN p_target;
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_deployment_target(bytea) FROM PUBLIC;
"""

# Frozen original Python 3.11 Unicode 14 identifier semantics. Regenerate only
# after an explicit model/runtime compatibility review, never from PG locale.
# Frozen Python 3.11 JSON decimal conversion limit; deployment must verify it.
CAPACITY_SIGNING_PERMIT_INTEGER_DIGITS = 4300
CAPACITY_SIGNING_PERMIT_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_signed_time(p_value jsonb)
RETURNS timestamptz LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  value text;
  local_value timestamp;
  offset_minutes integer := 0;
  zone text;
BEGIN
  IF p_value IS NULL OR pg_catalog.jsonb_typeof(p_value) IS DISTINCT FROM 'string' THEN
    RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
  END IF;
  value := p_value #>> ARRAY[]::text[];
  IF value COLLATE "C" !~ '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{6})?(Z|[+-]([01][0-9]|2[0-3]):[0-5][0-9])$'
      OR value ~ '\.000000(Z|[+-])' OR value ~ '[+-]00:00$'
      OR pg_catalog.left(value,4) = '0000' THEN
    RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
  END IF;
  -- Python accepts offsets through 23:59; PG's direct timezone parser does not.
  -- Parse the bounded local date separately and apply the explicit offset.
  IF pg_catalog.right(value,1) = 'Z' THEN
    local_value := pg_catalog.left(value,pg_catalog.length(value)-1)::timestamp;
  ELSE
    zone := pg_catalog.right(value,6);
    offset_minutes := (pg_catalog.substr(zone,2,2)::integer*60
                       +pg_catalog.substr(zone,5,2)::integer)
                      * CASE WHEN pg_catalog.left(zone,1)='-' THEN -1 ELSE 1 END;
    local_value := pg_catalog.left(value,pg_catalog.length(value)-6)::timestamp;
  END IF;
  RETURN (local_value - offset_minutes * interval '1 minute') AT TIME ZONE 'UTC';
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_signed_time(jsonb) FROM PUBLIC;

CREATE FUNCTION aos_capacity_publication_private.read_signing_permit(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  document jsonb;
  policy_ref jsonb;
  field text;
  public_key text;
  starts_at timestamptz;
  ends_at timestamptz;
BEGIN
  document := aos_capacity_publication_private.read_signed_body(p_raw);
  IF document IS NULL OR pg_catalog.jsonb_typeof(document) IS DISTINCT FROM 'object'
      OR NOT (document ?& ARRAY['schemaVersion','tenant','assetId','revision','publisher',
        'keyId','validFrom','validUntil','deploymentTarget','purpose','sourcePolicyRef',
        'signerPublisher','signerKeyId','signerRootRevision','signerPublicKey'])
      OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(document)) <> 15 THEN
    RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF document->'tenant' IS DISTINCT FROM '{"orgId":"org-org","projectId":"dev-project"}'::jsonb
      OR document->'schemaVersion' IS DISTINCT FROM '1'::jsonb
      OR pg_catalog.jsonb_typeof(document->'revision') IS DISTINCT FROM 'number'
      OR (document->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$'
      OR pg_catalog.length(document->>'revision') > 4300
      OR document->'purpose' IS DISTINCT FROM '"provider_capacity_source_signing_permit"'::jsonb THEN
    RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOREACH field IN ARRAY ARRAY['assetId','publisher','keyId','signerPublisher','signerKeyId'] LOOP
    PERFORM aos_capacity_publication_private.read_identifier(document->field);
  END LOOP;
  PERFORM aos_capacity_publication_private.read_deployment_target(pg_catalog.convert_to(
      aos_capacity_publication_private.canonical_signed_json((document->'deploymentTarget')::json,1),'UTF8'));
  policy_ref := document->'sourcePolicyRef';
  IF pg_catalog.jsonb_typeof(policy_ref) IS DISTINCT FROM 'object'
      OR NOT (policy_ref ?& ARRAY['assetType','assetId','revision','contentHash'])
      OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(policy_ref)) <> 4
      OR policy_ref->'assetType' IS DISTINCT FROM '"ProviderCapacitySourcePolicyRevision"'::jsonb
      OR pg_catalog.jsonb_typeof(policy_ref->'revision') IS DISTINCT FROM 'number'
      OR (policy_ref->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$'
      OR pg_catalog.length(policy_ref->>'revision') > 4300
      OR pg_catalog.jsonb_typeof(policy_ref->'contentHash') IS DISTINCT FROM 'string'
      OR (policy_ref->>'contentHash') COLLATE "C" !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
  END IF;
  PERFORM aos_capacity_publication_private.read_identifier(policy_ref->'assetId');
  IF pg_catalog.jsonb_typeof(document->'signerRootRevision') IS DISTINCT FROM 'string'
      OR (document->>'signerRootRevision') COLLATE "C" !~ '^sha256:[0-9a-f]{64}$'
      OR pg_catalog.jsonb_typeof(document->'signerPublicKey') IS DISTINCT FROM 'string' THEN
    RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
  END IF;
  public_key := document->>'signerPublicKey';
  IF pg_catalog.length(public_key) <> 44
      OR pg_catalog.octet_length(pg_catalog.decode(public_key,'base64')) <> 32
      OR pg_catalog.encode(pg_catalog.decode(public_key,'base64'),'base64') <> public_key THEN
    RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
  END IF;
  starts_at := aos_capacity_publication_private.read_signed_time(document->'validFrom');
  ends_at := aos_capacity_publication_private.read_signed_time(document->'validUntil');
  IF ends_at <= starts_at OR extract(epoch FROM ends_at-starts_at) > 31622400 THEN
    RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
  END IF;
  RETURN document;
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_SIGNING_PERMIT_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_signing_permit(bytea) FROM PUBLIC;
"""

CAPACITY_IDENTIFIER_UNICODE_VERSION = '14.0.0'
CAPACITY_IDENTIFIER_RANGES_SHA256 = '455c3fa3aed3a66f57dca53b768cb7c62b01e753139e5fe2849b3ffb5385fe4a'
CAPACITY_IDENTIFIER_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_identifier(p_value jsonb)
RETURNS text LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  starts integer[] := ARRAY[33,161,174,890,900,908,910,931,1329,1369,1421,1425,1488,1519,1542,1565,1758,1808,1869,1984,2045,2096,2112,2142,2144,2160,2200,2275,2437,2447,2451,2474,2482,2486,2492,2503,2507,2519,2524,2527,2534,2561,2565,2575,2579,2602,2610,2613,2616,2620,2622,2631,2635,2641,2649,2654,2662,2689,2693,2703,2707,2730,2738,2741,2748,2759,2763,2768,2784,2790,2809,2817,2821,2831,2835,2858,2866,2869,2876,2887,2891,2901,2908,2911,2918,2946,2949,2958,2962,2969,2972,2974,2979,2984,2990,3006,3014,3018,3024,3031,3046,3072,3086,3090,3114,3132,3142,3146,3157,3160,3165,3168,3174,3191,3214,3218,3242,3253,3260,3270,3274,3285,3293,3296,3302,3313,3328,3342,3346,3398,3402,3412,3430,3457,3461,3482,3507,3517,3520,3530,3535,3542,3544,3558,3570,3585,3647,3713,3716,3718,3724,3749,3751,3776,3782,3784,3792,3804,3840,3913,3953,3993,4030,4046,4096,4295,4301,4304,4682,4688,4696,4698,4704,4746,4752,4786,4792,4800,4802,4808,4824,4882,4888,4957,4992,5024,5112,5120,5761,5792,5888,5919,5952,5984,5998,6002,6016,6112,6128,6144,6159,6176,6272,6320,6400,6432,6448,6464,6468,6512,6528,6576,6608,6622,6686,6752,6783,6800,6816,6832,6912,6992,7040,7164,7227,7245,7312,7357,7376,7424,7960,7968,8008,8016,8025,8027,8029,8031,8064,8118,8134,8150,8157,8178,8182,8208,8240,8304,8308,8336,8352,8400,8448,8592,9280,9312,11126,11159,11513,11559,11565,11568,11631,11647,11680,11688,11696,11704,11712,11720,11728,11736,11744,11904,11931,12032,12272,12289,12353,12441,12549,12593,12688,12784,12832,42128,42192,42560,42752,42960,42963,42965,42994,43056,43072,43136,43214,43232,43359,43392,43471,43486,43520,43584,43600,43612,43739,43777,43785,43793,43808,43816,43824,43888,44016,44032,55216,55243,63744,64112,64256,64275,64285,64312,64318,64320,64323,64326,64467,64914,64975,65008,65056,65108,65128,65136,65142,65281,65474,65482,65490,65498,65504,65512,65532,65536,65549,65576,65596,65599,65616,65664,65792,65799,65847,65936,65952,66000,66176,66208,66272,66304,66349,66384,66432,66463,66504,66560,66720,66736,66776,66816,66864,66927,66940,66956,66964,66967,66979,66995,67003,67072,67392,67424,67456,67463,67506,67584,67592,67594,67639,67644,67647,67671,67751,67808,67828,67835,67871,67903,67968,68028,68050,68101,68108,68117,68121,68152,68159,68176,68192,68288,68331,68352,68409,68440,68472,68505,68521,68608,68736,68800,68858,68912,69216,69248,69291,69296,69376,69424,69488,69552,69600,69632,69714,69759,69822,69840,69872,69888,69942,69968,70016,70113,70144,70163,70272,70280,70282,70287,70303,70320,70384,70400,70405,70415,70419,70442,70450,70453,70459,70471,70475,70480,70487,70493,70502,70512,70656,70749,70784,70864,71040,71096,71168,71248,71264,71296,71360,71424,71453,71472,71680,71840,71935,71945,71948,71957,71960,71991,71995,72016,72096,72106,72154,72192,72272,72368,72704,72714,72760,72784,72816,72850,72873,72960,72968,72971,73018,73020,73023,73040,73056,73063,73066,73104,73107,73120,73440,73648,73664,73727,74752,74864,74880,77712,77824,82944,92160,92736,92768,92782,92864,92880,92912,92928,93008,93019,93027,93053,93760,93952,94031,94095,94176,94192,94208,100352,101632,110576,110581,110589,110592,110928,110948,110960,113664,113776,113792,113808,113820,118528,118576,118608,118784,119040,119081,119163,119296,119520,119552,119648,119808,119894,119966,119970,119973,119977,119982,119995,119997,120005,120071,120077,120086,120094,120123,120128,120134,120138,120146,120488,120782,121499,121505,122624,122880,122888,122907,122915,122918,123136,123184,123200,123214,123536,123584,123647,124896,124904,124909,124912,124928,125127,125184,125264,125278,126065,126209,126464,126469,126497,126500,126503,126505,126516,126521,126523,126530,126535,126537,126539,126541,126545,126548,126551,126553,126555,126557,126559,126561,126564,126567,126572,126580,126585,126590,126592,126603,126625,126629,126635,126704,126976,127024,127136,127153,127169,127185,127232,127462,127504,127552,127568,127584,127744,128733,128752,128768,128896,128992,129008,129024,129040,129104,129120,129168,129200,129280,129632,129648,129656,129664,129680,129712,129728,129744,129760,129776,129792,129940,130032,131072,173824,177984,178208,183984,194560,196608,917760];
  ends integer[] := ARRAY[126,172,887,895,906,908,929,1327,1366,1418,1423,1479,1514,1524,1563,1756,1805,1866,1969,2042,2093,2110,2139,2142,2154,2190,2273,2435,2444,2448,2472,2480,2482,2489,2500,2504,2510,2519,2525,2531,2558,2563,2570,2576,2600,2608,2611,2614,2617,2620,2626,2632,2637,2641,2652,2654,2678,2691,2701,2705,2728,2736,2739,2745,2757,2761,2765,2768,2787,2801,2815,2819,2828,2832,2856,2864,2867,2873,2884,2888,2893,2903,2909,2915,2935,2947,2954,2960,2965,2970,2972,2975,2980,2986,3001,3010,3016,3021,3024,3031,3066,3084,3088,3112,3129,3140,3144,3149,3158,3162,3165,3171,3183,3212,3216,3240,3251,3257,3268,3272,3277,3286,3294,3299,3311,3314,3340,3344,3396,3400,3407,3427,3455,3459,3478,3505,3515,3517,3526,3530,3540,3542,3551,3567,3572,3642,3675,3714,3716,3722,3747,3749,3773,3780,3782,3789,3801,3807,3911,3948,3991,4028,4044,4058,4293,4295,4301,4680,4685,4694,4696,4701,4744,4749,4784,4789,4798,4800,4805,4822,4880,4885,4954,4988,5017,5109,5117,5759,5788,5880,5909,5942,5971,5996,6000,6003,6109,6121,6137,6157,6169,6264,6314,6389,6430,6443,6459,6464,6509,6516,6571,6601,6618,6683,6750,6780,6793,6809,6829,6862,6988,7038,7155,7223,7241,7304,7354,7367,7418,7957,7965,8005,8013,8023,8025,8027,8029,8061,8116,8132,8147,8155,8175,8180,8190,8231,8286,8305,8334,8348,8384,8432,8587,9254,9290,11123,11157,11507,11557,11559,11565,11623,11632,11670,11686,11694,11702,11710,11718,11726,11734,11742,11869,11929,12019,12245,12283,12351,12438,12543,12591,12686,12771,12830,42124,42182,42539,42743,42954,42961,42963,42969,43052,43065,43127,43205,43225,43347,43388,43469,43481,43518,43574,43597,43609,43714,43766,43782,43790,43798,43814,43822,43883,44013,44025,55203,55238,55291,64109,64217,64262,64279,64310,64316,64318,64321,64324,64450,64911,64967,64975,65049,65106,65126,65131,65140,65276,65470,65479,65487,65495,65500,65510,65518,65533,65547,65574,65594,65597,65613,65629,65786,65794,65843,65934,65948,65952,66045,66204,66256,66299,66339,66378,66426,66461,66499,66517,66717,66729,66771,66811,66855,66915,66938,66954,66962,66965,66977,66993,67001,67004,67382,67413,67431,67461,67504,67514,67589,67592,67637,67640,67644,67669,67742,67759,67826,67829,67867,67897,67903,68023,68047,68099,68102,68115,68119,68149,68154,68168,68184,68255,68326,68342,68405,68437,68466,68497,68508,68527,68680,68786,68850,68903,68921,69246,69289,69293,69297,69415,69465,69513,69579,69622,69709,69749,69820,69826,69864,69881,69940,69959,70006,70111,70132,70161,70206,70278,70280,70285,70301,70313,70378,70393,70403,70412,70416,70440,70448,70451,70457,70468,70472,70477,70480,70487,70499,70508,70516,70747,70753,70855,70873,71093,71133,71236,71257,71276,71353,71369,71450,71467,71494,71739,71922,71942,71945,71955,71958,71989,71992,72006,72025,72103,72151,72164,72263,72354,72440,72712,72758,72773,72812,72847,72871,72886,72966,72969,73014,73018,73021,73031,73049,73061,73064,73102,73105,73112,73129,73464,73648,73713,74649,74862,74868,75075,77810,78894,83526,92728,92766,92777,92862,92873,92909,92917,92997,93017,93025,93047,93071,93850,94026,94087,94111,94180,94193,100343,101589,101640,110579,110587,110590,110882,110930,110951,111355,113770,113788,113800,113817,113823,118573,118598,118723,119029,119078,119154,119274,119365,119539,119638,119672,119892,119964,119967,119970,119974,119980,119993,119995,120003,120069,120074,120084,120092,120121,120126,120132,120134,120144,120485,120779,121483,121503,121519,122654,122886,122904,122913,122916,122922,123180,123197,123209,123215,123566,123641,123647,124902,124907,124910,124926,125124,125142,125259,125273,125279,126132,126269,126467,126495,126498,126500,126503,126514,126519,126521,126523,126530,126535,126537,126539,126543,126546,126548,126551,126553,126555,126557,126559,126562,126564,126570,126578,126583,126588,126590,126601,126619,126627,126633,126651,126705,127019,127123,127150,127167,127183,127221,127405,127490,127547,127560,127569,127589,128727,128748,128764,128883,128984,129003,129008,129035,129095,129113,129159,129197,129201,129619,129645,129652,129660,129670,129708,129722,129733,129753,129767,129782,129938,129994,130041,173791,177976,178205,183969,191456,195101,201546,917999];
  value text;
  codepoint integer;
  position integer;
  low_index integer;
  high_index integer;
  middle_index integer;
  found boolean;
BEGIN
  IF p_value IS NULL OR pg_catalog.jsonb_typeof(p_value) IS DISTINCT FROM 'string'
      OR pg_catalog.current_setting('server_encoding') <> 'UTF8' THEN
    RAISE EXCEPTION 'CAPACITY_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
  END IF;
  value := p_value #>> ARRAY[]::text[];
  IF pg_catalog.char_length(value) NOT BETWEEN 1 AND 200 THEN
    RAISE EXCEPTION 'CAPACITY_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOR position IN 1..pg_catalog.char_length(value) LOOP
    codepoint := pg_catalog.ascii(pg_catalog.substr(value,position,1));
    low_index := 1;
    high_index := pg_catalog.array_length(starts,1);
    found := false;
    WHILE low_index <= high_index LOOP
      middle_index := (low_index+high_index)/2;
      IF codepoint < starts[middle_index] THEN
        high_index := middle_index-1;
      ELSIF codepoint > ends[middle_index] THEN
        low_index := middle_index+1;
      ELSE
        found := true;
        EXIT;
      END IF;
    END LOOP;
    IF NOT found THEN
      RAISE EXCEPTION 'CAPACITY_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
    END IF;
  END LOOP;
  RETURN value;
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_IDENTIFIER_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_identifier(jsonb) FROM PUBLIC;
"""

# Structure only. Trusted deployment, anchor, signature and epochs are checked
# by the independent registration transaction, never by this parser's result.
CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_origin_bootstrap(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  document jsonb;
  field text;
  ref jsonb;
  refs jsonb;
  starts_at timestamptz;
  ends_at timestamptz;
BEGIN
  document := aos_capacity_publication_private.read_signed_body(p_raw);
  IF document IS NULL OR pg_catalog.jsonb_typeof(document) IS DISTINCT FROM 'object'
      OR NOT (document ?& ARRAY['schemaVersion','tenant','assetId','revision','publisher',
        'keyId','validFrom','validUntil','deploymentTarget','purpose','bootstrapId',
        'publisherSubject','policyPublisherRole','anchorRevision','rootSnapshotHash','allowedDocumentRefs'])
      OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(document)) <> 16 THEN
    RAISE EXCEPTION 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF document->'tenant' IS DISTINCT FROM '{"orgId":"org-org","projectId":"dev-project"}'::jsonb
      OR document->'schemaVersion' IS DISTINCT FROM '1'::jsonb
      OR pg_catalog.jsonb_typeof(document->'revision') IS DISTINCT FROM 'number'
      OR (document->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$'
      OR pg_catalog.length(document->>'revision') > 4300
      OR document->'purpose' IS DISTINCT FROM '"provider_capacity_origin_bootstrap"'::jsonb
      OR document->'policyPublisherRole' IS DISTINCT FROM '"aos_provider_capacity_policy_publisher"'::jsonb THEN
    RAISE EXCEPTION 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOREACH field IN ARRAY ARRAY['assetId','publisher','keyId','bootstrapId','publisherSubject'] LOOP
    PERFORM aos_capacity_publication_private.read_identifier(document->field);
  END LOOP;
  FOREACH field IN ARRAY ARRAY['anchorRevision','rootSnapshotHash'] LOOP
    IF pg_catalog.jsonb_typeof(document->field) IS DISTINCT FROM 'string'
        OR (document->>field) COLLATE "C" !~ '^sha256:[0-9a-f]{64}$' THEN
      RAISE EXCEPTION 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' USING ERRCODE='22023';
    END IF;
  END LOOP;
  PERFORM aos_capacity_publication_private.read_deployment_target(pg_catalog.convert_to(
      aos_capacity_publication_private.canonical_signed_json((document->'deploymentTarget')::json,1),'UTF8'));
  refs := document->'allowedDocumentRefs';
  IF pg_catalog.jsonb_typeof(refs) IS DISTINCT FROM 'array'
      OR pg_catalog.jsonb_array_length(refs) NOT BETWEEN 1 AND 1000 THEN
    RAISE EXCEPTION 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOR ref IN SELECT value FROM pg_catalog.jsonb_array_elements(refs) LOOP
    IF pg_catalog.jsonb_typeof(ref) IS DISTINCT FROM 'object'
        OR NOT (ref ?& ARRAY['assetType','assetId','revision','contentHash'])
        OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(ref)) <> 4
        OR ref->'assetType' NOT IN ('"ProviderCapacitySourcePolicyRevision"'::jsonb,
          '"SupplierCapacityAttestationRevision"'::jsonb,'"ProviderCapacitySigningPermitRevision"'::jsonb)
        OR pg_catalog.jsonb_typeof(ref->'revision') IS DISTINCT FROM 'number'
        OR (ref->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$'
        OR pg_catalog.length(ref->>'revision') > 4300
        OR pg_catalog.jsonb_typeof(ref->'contentHash') IS DISTINCT FROM 'string'
        OR (ref->>'contentHash') COLLATE "C" !~ '^[0-9a-f]{64}$' THEN
      RAISE EXCEPTION 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' USING ERRCODE='22023';
    END IF;
    PERFORM aos_capacity_publication_private.read_identifier(ref->'assetId');
  END LOOP;
  IF (SELECT count(*) FROM (SELECT DISTINCT value->'assetType',value->'assetId'
      FROM pg_catalog.jsonb_array_elements(refs)) unique_refs) <> pg_catalog.jsonb_array_length(refs) THEN
    RAISE EXCEPTION 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' USING ERRCODE='22023';
  END IF;
  starts_at := aos_capacity_publication_private.read_signed_time(document->'validFrom');
  ends_at := aos_capacity_publication_private.read_signed_time(document->'validUntil');
  IF ends_at <= starts_at OR extract(epoch FROM ends_at-starts_at) > 31622400 THEN
    RAISE EXCEPTION 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' USING ERRCODE='22023';
  END IF;
  RETURN document;
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_origin_bootstrap(bytea) FROM PUBLIC;
"""


def _original_approval_snapshot_predicate():
    """Reuse original dedicated metadata/policy, never an approval state machine.

    This snapshot predicate takes no new locks. A complete publication caller
    must hold the original Guard prefixes and recheck all typed dependencies;
    matching these rows alone cannot authenticate, sign or publish a Source.
    """
    from aos_api.aip_provider_capacity_action import ProviderCapacityActionGuard
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import canonical_hash
    from aos_api.asset_registry.canonical_json import canonical_json
    def literal(value):
        return "'"+canonical_json(value).decode().replace("'","''")+"'::jsonb"
    alternatives=[]
    for guard,purpose in ((ProviderCapacityActionGuard,'capacity-allocation'),
                          (ProviderCapacitySourceActionGuard,'capacity-source-review')):
        snapshot={**guard.action_snapshot,'revisionHash':canonical_hash(guard.action_snapshot)}
        risk=classify_action_risk(guard.action_id,snapshot,{},None)
        policy=dict(floor=risk.floor.value,reasons=list(risk.reasons),**risk.approval_policy)
        alternatives.append(f"""(p.action_type_id='{guard.action_id}' AND p.purpose='{purpose}'
          AND p.action_type_snapshot={literal(snapshot)} AND p.policy_snapshot={literal(policy)}
          AND p.risk_level='{risk.level.value}'
          AND EXISTS(SELECT 1 FROM public.meta_object_type o WHERE o.id='{guard.object_id}'
            AND pg_catalog.jsonb_build_object('id',o.id,'name',o.name,'description',o.description,
              'published',o.published,'properties',o.properties,'required_markings',o.required_markings)
              ={literal(guard.object_snapshot)})
          AND EXISTS(SELECT 1 FROM public.meta_action_type a WHERE a.id='{guard.action_id}'
            AND pg_catalog.jsonb_build_object('id',a.id,'name',a.name,'objectType',a.object_type,
              'parameters',a.parameters,'requiredMarkings',a.required_markings,
              'submissionCriteria',a.submission_criteria)={literal(guard.action_snapshot)}))""")
    return "\n AND ("+" OR ".join(alternatives)+r"""
 ) AND p.task_id IS NULL AND p.run_id IS NULL AND (p.object_ref IS NULL OR p.object_ref='null'::jsonb)
   AND p.impact_preview_id IS NULL AND p.client_risk_hint IS NULL
   AND p.diff='{}'::jsonb AND p.evidence_refs='[]'::jsonb
   AND p.approval_policy_hash=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
     public.canonical_asset_registry_jsonb(p.policy_snapshot),'UTF8')),'hex')
   AND EXISTS(SELECT 1 FROM public.aip_action_draft d
     WHERE (d.org_id,d.project_id,d.proposal_id)=(p.org_id,p.project_id,p.proposal_id)
       AND d.status='approved'
       AND pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
         public.canonical_asset_registry_jsonb(d.snapshot),'UTF8')),'hex')=p.proposal_hash
       AND d.snapshot->'actionType'=p.action_type_snapshot AND d.snapshot->'payload'=p.payload
       AND d.snapshot->'policy'=p.policy_snapshot
       AND d.snapshot->>'actionBindingHash'=p.action_binding_hash)
   AND e.value->'actor'->>'actorId'<>p.created_by
   AND e.value->>'eligibilitySnapshotHash'=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
     public.canonical_asset_registry_jsonb(pg_catalog.jsonb_build_object(
       'tenant',pg_catalog.jsonb_build_object('orgId',p.org_id,'projectId',p.project_id),
       'actorId',e.value->'actor'->>'actorId','roles',pg_catalog.jsonb_build_array('owner'),
       'slotId','checker.1','approvalPolicyHash',p.approval_policy_hash)),'UTF8')),'hex')
   AND (SELECT count(*) FROM public.meta_membership m
     WHERE (m.org_id,m.project_id,m.subject)=(p.org_id,p.project_id,p.created_by))=1
   AND EXISTS(SELECT 1 FROM public.meta_membership m
     WHERE (m.org_id,m.project_id,m.subject)=(p.org_id,p.project_id,p.created_by)
       AND pg_catalog.lower(m.role)='owner')
   AND (SELECT count(*) FROM public.meta_membership m
     WHERE (m.org_id,m.project_id,m.subject)=(p.org_id,p.project_id,e.value->'actor'->>'actorId'))=1
   AND EXISTS(SELECT 1 FROM public.meta_membership m
     WHERE (m.org_id,m.project_id,m.subject)=(p.org_id,p.project_id,e.value->'actor'->>'actorId')
       AND pg_catalog.lower(m.role)='owner')
"""


# S03/S04/S08 original row fence. This is consumed after private identity
# validation; every original Guard check and withdrawal epoch still follows.
_CAPACITY_APPROVED_ROW_SQL = (
    "WITH exact_event AS (" + CAPACITY_APPROVAL_EVENT_PROJECTION_SQL + r"""
)
SELECT p.* FROM public.aip_action_proposal p
JOIN exact_event e ON e.proposal_id=p.proposal_id
WHERE p.org_id=%(org_id)s AND p.project_id=%(project_id)s
  AND p.org_id='org-org' AND p.project_id='dev-project'
  AND p.created_by=%(maker)s AND p.status='approved' AND p.version=2
  AND p.expires_at > pg_catalog.clock_timestamp()
  AND e.hash=%(approval_event_hash)s
  AND e.value->'proposalVersion'='1'::jsonb
  AND e.value->'decision'='"approved"'::jsonb
  AND e.value->'slotId'='"checker.1"'::jsonb
  AND e.value->>'proposalHash'=p.proposal_hash
  AND e.value->>'actionBindingHash'=p.action_binding_hash
  AND e.value->>'approvalPolicyHash'=p.approval_policy_hash
  AND EXISTS (SELECT 1 FROM public.aip_action_approval_event current_event
    WHERE current_event.org_id=p.org_id AND current_event.project_id=p.project_id
      AND current_event.proposal_id=p.proposal_id
      AND current_event.approval_event_id=%(approval_event_id)s
      AND current_event.expires_at > pg_catalog.clock_timestamp())
  AND (SELECT count(*) FROM public.aip_action_approval_event all_events
    WHERE all_events.org_id=p.org_id AND all_events.project_id=p.project_id
      AND all_events.proposal_id=p.proposal_id)=1
"""
)


CAPACITY_APPROVED_SOURCE_ROW_SQL = _CAPACITY_APPROVED_ROW_SQL + _original_approval_snapshot_predicate() + r"""
  AND p.action_type_id='aip_review_provider_capacity_source'
  AND p.proposal_id=%(proposal_id)s AND p.version=%(proposal_revision)s
  AND p.proposal_hash=%(proposal_hash)s
FOR SHARE OF p
"""

# S10 runs only after the private reader has held every original Guard fence.
# Do not add or reorder locks in this snapshot query.
CAPACITY_APPROVED_ALLOCATION_ROW_SQL = _CAPACITY_APPROVED_ROW_SQL + _original_approval_snapshot_predicate() + r"""
  AND p.action_type_id='aip_request_provider_capacity'
  AND p.payload=pg_catalog.jsonb_build_object('requestId',%(request_id)s::text,
                                            'requestHash',%(request_hash)s::text)
  AND p.action_binding_hash=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
    public.canonical_asset_registry_jsonb(pg_catalog.jsonb_build_object(
      'requestId',p.payload->'requestId','requestHash',p.payload->'requestHash',
      'actionTypeRevisionHash',p.action_type_snapshot->'revisionHash')),'UTF8')),'hex')
"""

# S17 complete policy shape only. Independent roots, signatures, current
# authority and deployment matching must be checked by the publication path.
CAPACITY_SOURCE_POLICY_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_source_policy(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  document jsonb;
  field text;
  modes jsonb;
  starts_at timestamptz;
  ends_at timestamptz;
BEGIN
  document := aos_capacity_publication_private.read_signed_body(p_raw);
  IF document IS NULL OR pg_catalog.jsonb_typeof(document) IS DISTINCT FROM 'object'
      OR NOT (document ?& ARRAY['schemaVersion','tenant','assetId','revision','publisher',
        'keyId','supplierId','validFrom','validUntil','purpose','attestationPublisher',
        'attestationKeyId','attestationRootRevision','maxObservationAgeSeconds',
        'maxFutureSkewSeconds','allowedTokenModes','deploymentTarget'])
      OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(document)) <> 17 THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_POLICY_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF document->'tenant' IS DISTINCT FROM '{"orgId":"org-org","projectId":"dev-project"}'::jsonb
      OR document->'schemaVersion' IS DISTINCT FROM '1'::jsonb
      OR document->'publisher' IS DISTINCT FROM '"aos-capacity-source-policy"'::jsonb
      OR document->'purpose' IS DISTINCT FROM '"provider_capacity_source"'::jsonb
      OR pg_catalog.jsonb_typeof(document->'revision') IS DISTINCT FROM 'number'
      OR (document->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$'
      OR pg_catalog.length(document->>'revision') > 4300
      OR pg_catalog.jsonb_typeof(document->'attestationRootRevision') IS DISTINCT FROM 'string'
      OR (document->>'attestationRootRevision') COLLATE "C" !~ '^sha256:[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_POLICY_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOREACH field IN ARRAY ARRAY['assetId','publisher','keyId','supplierId','attestationPublisher','attestationKeyId'] LOOP
    PERFORM aos_capacity_publication_private.read_identifier(document->field);
  END LOOP;
  IF pg_catalog.jsonb_typeof(document->'maxObservationAgeSeconds') IS DISTINCT FROM 'number'
      OR (document->>'maxObservationAgeSeconds') COLLATE "C" !~ '^[1-9][0-9]*$'
      OR pg_catalog.length(document->>'maxObservationAgeSeconds') > 5
      OR pg_catalog.jsonb_typeof(document->'maxFutureSkewSeconds') IS DISTINCT FROM 'number'
      OR (document->>'maxFutureSkewSeconds') COLLATE "C" !~ '^(0|[1-9][0-9]*)$'
      OR pg_catalog.length(document->>'maxFutureSkewSeconds') > 2 THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_POLICY_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF (document->>'maxObservationAgeSeconds')::integer NOT BETWEEN 1 AND 86400
      OR (document->>'maxFutureSkewSeconds')::integer NOT BETWEEN 0 AND 60 THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_POLICY_REQUIRED' USING ERRCODE='22023';
  END IF;
  modes := document->'allowedTokenModes';
  IF pg_catalog.jsonb_typeof(modes) IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_POLICY_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF pg_catalog.jsonb_array_length(modes) NOT BETWEEN 1 AND 2
      OR EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(modes) AS refs(value)
        WHERE value NOT IN ('"inflight_upper_bound"'::jsonb,'"fixed_window_rate"'::jsonb))
      OR (SELECT count(DISTINCT value) FROM pg_catalog.jsonb_array_elements(modes))
          <> pg_catalog.jsonb_array_length(modes) THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_POLICY_REQUIRED' USING ERRCODE='22023';
  END IF;
  PERFORM aos_capacity_publication_private.read_deployment_target(pg_catalog.convert_to(
      aos_capacity_publication_private.canonical_signed_json((document->'deploymentTarget')::json,1),'UTF8'));
  starts_at := aos_capacity_publication_private.read_signed_time(document->'validFrom');
  ends_at := aos_capacity_publication_private.read_signed_time(document->'validUntil');
  IF ends_at <= starts_at OR extract(epoch FROM ends_at-starts_at) > 31622400 THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_POLICY_REQUIRED' USING ERRCODE='22023';
  END IF;
  RETURN document;
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_POLICY_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_source_policy(bytea) FROM PUBLIC;
"""

# S17/S18 complete supplier shape; this never authenticates the supplier.
CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_supplier_attestation(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  document jsonb;
  field text;
  refs jsonb;
  ref jsonb;
  token jsonb;
  starts_at timestamptz;
  ends_at timestamptz;
  observed_at timestamptz;
BEGIN
  document := aos_capacity_publication_private.read_signed_body(p_raw);
  IF document IS NULL OR pg_catalog.jsonb_typeof(document) IS DISTINCT FROM 'object'
      OR NOT (document ?& ARRAY['schemaVersion','tenant','assetId','revision','publisher','keyId',
        'supplierId','validFrom','validUntil','purpose','supplierAccountFingerprint','providerRefs',
        'evidenceRef','maxConcurrency','tokenLimit','observedAt'])
      OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(document)) <> 16 THEN
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF document->'tenant' IS DISTINCT FROM '{"orgId":"org-org","projectId":"dev-project"}'::jsonb
      OR document->'schemaVersion' IS DISTINCT FROM '1'::jsonb
      OR document->'purpose' IS DISTINCT FROM '"supplier_capacity_attestation"'::jsonb
      OR pg_catalog.jsonb_typeof(document->'revision') IS DISTINCT FROM 'number'
      OR (document->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$'
      OR pg_catalog.length(document->>'revision') > 4300
      OR pg_catalog.jsonb_typeof(document->'supplierAccountFingerprint') IS DISTINCT FROM 'string'
      OR (document->>'supplierAccountFingerprint') COLLATE "C" !~ '^[0-9a-f]{64}$'
      OR pg_catalog.jsonb_typeof(document->'maxConcurrency') IS DISTINCT FROM 'number'
      OR (document->>'maxConcurrency') COLLATE "C" !~ '^[1-9][0-9]*$'
      OR pg_catalog.length(document->>'maxConcurrency') > 7 THEN
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF (document->>'maxConcurrency')::integer NOT BETWEEN 1 AND 1000000 THEN
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOREACH field IN ARRAY ARRAY['assetId','publisher','keyId','supplierId'] LOOP
    PERFORM aos_capacity_publication_private.read_identifier(document->field);
  END LOOP;
  refs := document->'providerRefs';
  IF pg_catalog.jsonb_typeof(refs) IS DISTINCT FROM 'array'
      OR pg_catalog.jsonb_array_length(refs) NOT BETWEEN 1 AND 1000 THEN
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  FOREACH field IN ARRAY ARRAY['providerRefs','evidenceRef'] LOOP
    refs := CASE WHEN field='providerRefs' THEN document->field
        ELSE pg_catalog.jsonb_build_array(document->field) END;
    FOR ref IN SELECT value FROM pg_catalog.jsonb_array_elements(refs) LOOP
      IF pg_catalog.jsonb_typeof(ref) IS DISTINCT FROM 'object'
          OR NOT (ref ?& ARRAY['assetType','assetId','revision','contentHash'])
          OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(ref)) <> 4
          OR ref->'assetType' IS DISTINCT FROM pg_catalog.to_jsonb(
            CASE WHEN field='providerRefs' THEN 'ProviderInstanceRevision'::text ELSE 'EvidenceBundleRevision'::text END)
          OR pg_catalog.jsonb_typeof(ref->'revision') IS DISTINCT FROM 'number'
          OR (ref->>'revision') COLLATE "C" !~ '^[1-9][0-9]*$'
          OR pg_catalog.length(ref->>'revision') > 4300
          OR pg_catalog.jsonb_typeof(ref->'contentHash') IS DISTINCT FROM 'string'
          OR (ref->>'contentHash') COLLATE "C" !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
      END IF;
      PERFORM aos_capacity_publication_private.read_identifier(ref->'assetId');
    END LOOP;
  END LOOP;
  IF (SELECT count(DISTINCT value->'assetId') FROM pg_catalog.jsonb_array_elements(document->'providerRefs'))
      <> pg_catalog.jsonb_array_length(document->'providerRefs') THEN
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  token := document->'tokenLimit';
  IF pg_catalog.jsonb_typeof(token) IS DISTINCT FROM 'object'
      OR NOT (token ?& ARRAY['mode','unit','maxTokens'])
      OR token->'unit' IS DISTINCT FROM '"token"'::jsonb
      OR pg_catalog.jsonb_typeof(token->'maxTokens') IS DISTINCT FROM 'number'
      OR (token->>'maxTokens') COLLATE "C" !~ '^[1-9][0-9]*$'
      OR pg_catalog.length(token->>'maxTokens') > 13 THEN
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF (token->>'maxTokens')::bigint NOT BETWEEN 1 AND 1000000000000 THEN
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  IF token->'mode'='"inflight_upper_bound"'::jsonb THEN
    IF (SELECT count(*) FROM pg_catalog.jsonb_object_keys(token)) <> 3 THEN
      RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
    END IF;
  ELSIF token->'mode'='"fixed_window_rate"'::jsonb THEN
    IF NOT (token ?& ARRAY['windowSeconds','windowAnchor'])
        OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(token)) <> 5
        OR pg_catalog.jsonb_typeof(token->'windowSeconds') IS DISTINCT FROM 'number'
        OR (token->>'windowSeconds') COLLATE "C" !~ '^[1-9][0-9]*$'
        OR pg_catalog.length(token->>'windowSeconds') > 5 THEN
      RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
    END IF;
    IF (token->>'windowSeconds')::integer NOT BETWEEN 1 AND 86400 THEN
      RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
    END IF;
    PERFORM aos_capacity_publication_private.read_signed_time(token->'windowAnchor');
  ELSE
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  starts_at := aos_capacity_publication_private.read_signed_time(document->'validFrom');
  ends_at := aos_capacity_publication_private.read_signed_time(document->'validUntil');
  observed_at := aos_capacity_publication_private.read_signed_time(document->'observedAt');
  IF ends_at <= starts_at OR extract(epoch FROM ends_at-starts_at) > 31622400 OR observed_at >= ends_at THEN
    RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
  END IF;
  RETURN document;
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_supplier_attestation(bytea) FROM PUBLIC;
"""


# Complete normalized root transport, independent of signed-document limits.
# Every returned row remains untrusted until an authorized anchored registration.
CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_root_time_literal(p_literal text)
RETURNS timestamptz LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path = pg_catalog AS $body$
DECLARE
  pieces text[];
  local_time timestamp;
  offset_micros bigint;
BEGIN
  pieces := pg_catalog.regexp_match(p_literal,
    '^"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]{6}))?([+-])([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.([0-9]{6}))?)?"$', 'c');
  IF pieces IS NULL OR pieces[1]::integer = 0
      OR pieces[4]::integer > 23 OR pieces[5]::integer > 59 OR pieces[6]::integer > 59
      OR pieces[9]::integer > 23 OR pieces[10]::integer > 59
      OR COALESCE(pieces[11],'0')::integer > 59
      OR pieces[7] = '000000' OR pieces[12] = '000000'
      OR (pieces[11] = '00' AND pieces[12] IS NULL) THEN
    RAISE EXCEPTION 'CAPACITY_ROOT_TIME_REQUIRED' USING ERRCODE='22023';
  END IF;
  offset_micros := (pieces[9]::bigint*3600+pieces[10]::bigint*60+
      COALESCE(pieces[11],'0')::bigint)*1000000+COALESCE(pieces[12],'0')::bigint;
  -- Original FileReader normalizes pure subsecond zero offsets to UTC.
  IF (offset_micros = 0 AND pieces[8] <> '+')
      OR (offset_micros > 0 AND offset_micros < 1000000) THEN
    RAISE EXCEPTION 'CAPACITY_ROOT_TIME_REQUIRED' USING ERRCODE='22023';
  END IF;
  local_time := pg_catalog.make_timestamp(pieces[1]::integer,pieces[2]::integer,pieces[3]::integer,
      pieces[4]::integer,pieces[5]::integer,
      pieces[6]::integer+COALESCE(pieces[7],'0')::integer/1000000.0);
  RETURN (local_time AT TIME ZONE 'UTC') - pg_catalog.make_interval(
      secs => (CASE WHEN pieces[8]='-' THEN -offset_micros ELSE offset_micros END)/1000000.0);
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_ROOT_TIME_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_root_time_literal(text) FROM PUBLIC;

CREATE FUNCTION aos_capacity_publication_private.read_root_snapshot(p_message bytea)
RETURNS TABLE(root_ordinal integer,publisher_literal text,key_id_literal text,
    publisher_codepoints integer[],key_id_codepoints integer[],public_key bytea,root_revision text,
    not_before timestamptz,not_after timestamptz,revoked_at timestamptz,canonical_root bytea)
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path = pg_catalog AS $body$
DECLARE
  document text;
  array_document json;
  row_count bigint;
  row_cursor integer := 16;
  original record;
  row_text text;
  pieces text[];
  previous_publisher integer[];
  previous_key integer[];
  literal_pattern constant text := $regex$"(?:[^"\\]|\\.)*"$regex$;
  root_pattern text;
BEGIN
  IF p_message IS NULL OR pg_catalog.octet_length(p_message) > 8388608
      OR pg_catalog.current_setting('server_encoding') <> 'UTF8' THEN
    RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
  END IF;
  document := pg_catalog.convert_from(p_message,'UTF8');
  IF pg_catalog.octet_length(document) <> pg_catalog.length(document)
      OR pg_catalog.left(document,15) <> '{"trustRoots":[' OR pg_catalog.right(document,2) <> ']}' THEN
    RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
  END IF;
  -- Object JSON functions decode surrogate literals. Keep each array row opaque.
  array_document := pg_catalog.substr(document,15,pg_catalog.length(document)-15)::json;
  -- Subsequent canonical checks use p_message; release the full UTF8 copy.
  document := NULL;
  root_pattern := '^\{"algorithm":"Ed25519","keyId":('||literal_pattern||
    '),"notAfter":('||literal_pattern||'),"notBefore":('||literal_pattern||
    '),"publicKey":"([A-Za-z0-9+/]{43}=)","publisher":('||literal_pattern||
    '),"revision":"(sha256:[0-9a-f]{64})","revokedAt":(null|'||literal_pattern||')\}$';
  FOR original IN SELECT value,ordinality FROM pg_catalog.json_array_elements(array_document) WITH ORDINALITY LOOP
    -- The running FOR query owns its evaluated JSON input. Do not retain a
    -- second full-array variable while materializing all typed root rows.
    array_document := NULL;
    row_count := original.ordinality;
    row_text := original.value::text;
    -- Compare each untouched row and separator directly to the original bytes.
    -- Reject canonical whitespace drift without joining full document copies.
    IF row_count > 10000 OR pg_catalog.substr(p_message,row_cursor,pg_catalog.octet_length(row_text)) <> pg_catalog.convert_to(row_text,'UTF8') THEN
      RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
    END IF;
    row_cursor := row_cursor + pg_catalog.octet_length(row_text);
    IF pg_catalog.substr(p_message,row_cursor,1) = pg_catalog.decode('2c','hex') THEN
      row_cursor := row_cursor + 1;
    ELSIF pg_catalog.substr(p_message,row_cursor,1) <> pg_catalog.decode('5d','hex') THEN
      RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
    END IF;
    pieces := pg_catalog.regexp_match(row_text,root_pattern,'c');
    IF pieces IS NULL THEN
      RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
    END IF;
    publisher_literal := pieces[5];
    key_id_literal := pieces[1];
    publisher_codepoints := aos_capacity_publication_private.read_root_identifier_literal(publisher_literal);
    key_id_codepoints := aos_capacity_publication_private.read_root_identifier_literal(key_id_literal);
    IF previous_publisher IS NOT NULL AND (publisher_codepoints < previous_publisher
        OR (publisher_codepoints = previous_publisher AND key_id_codepoints <= previous_key)) THEN
      RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
    END IF;
    previous_publisher := publisher_codepoints;
    previous_key := key_id_codepoints;
    public_key := pg_catalog.decode(pieces[4],'base64');
    IF pg_catalog.octet_length(public_key) <> 32 OR pg_catalog.encode(public_key,'base64') <> pieces[4] THEN
      RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
    END IF;
    root_revision := pieces[6];
    not_before := aos_capacity_publication_private.read_root_time_literal(pieces[3]);
    not_after := aos_capacity_publication_private.read_root_time_literal(pieces[2]);
    revoked_at := CASE WHEN pieces[7]='null' THEN NULL
      ELSE aos_capacity_publication_private.read_root_time_literal(pieces[7]) END;
    IF not_before >= not_after THEN
      RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
    END IF;
    root_ordinal := original.ordinality;
    canonical_root := pg_catalog.convert_to(row_text,'UTF8');
    RETURN NEXT;
  END LOOP;
  IF pg_catalog.substr(p_message,row_cursor) <> pg_catalog.decode('5d7d','hex') THEN
    RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
  END IF;
  -- PL/pgSQL materializes the set: later rejection cannot expose a partial set.
EXCEPTION WHEN OTHERS THEN
  RAISE EXCEPTION 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' USING ERRCODE='22023';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_root_snapshot(bytea) FROM PUBLIC;
"""


# Untrusted original-model normalization for the future complete Source entry.
# Not installed by existing migrations, and never an approval or signature gate.
CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.original_source_field(p jsonb,camel text,snake text)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
BEGIN
 IF jsonb_typeof(p)<>'object' OR (camel=snake AND NOT p ? camel)
   OR (camel<>snake AND (p ? camel)=(p ? snake)) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_FIELD' USING ERRCODE='22023';
 END IF;
 RETURN COALESCE(p->camel,p->snake);
END $body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.original_source_field(jsonb,text,text) FROM PUBLIC;
ALTER FUNCTION aos_capacity_publication_private.original_source_field(jsonb,text,text) OWNER TO aos_capacity_publication_owner;

CREATE FUNCTION aos_capacity_publication_private.original_source_ref(p jsonb,kind text)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE t jsonb; i jsonb; r jsonb; h jsonb; trims text;
BEGIN
 IF jsonb_typeof(p)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(p))<>4
   OR p-ARRAY['assetType','asset_type','assetId','asset_id','revision','contentHash','content_hash']<>'{}'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_REF' USING ERRCODE='22023';
 END IF;
 t:=aos_capacity_publication_private.original_source_field(p,'assetType','asset_type');
 i:=aos_capacity_publication_private.original_source_field(p,'assetId','asset_id');
 r:=aos_capacity_publication_private.original_source_field(p,'revision','revision');
 h:=aos_capacity_publication_private.original_source_field(p,'contentHash','content_hash');
 SELECT string_agg(chr(point),'') INTO trims FROM unnest(ARRAY[9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288]) point;
 IF jsonb_typeof(t)<>'string' OR t#>>'{}'<>kind OR length(t#>>'{}') NOT BETWEEN 1 AND 80
   OR jsonb_typeof(i)<>'string' OR length(i#>>'{}') NOT BETWEEN 1 AND 200
   OR i#>>'{}'<>btrim(i#>>'{}',trims)
   OR jsonb_typeof(r)<>'number' OR (r#>>'{}') COLLATE "C" !~ '^[1-9][0-9]*$'
   OR jsonb_typeof(h)<>'string' OR (h#>>'{}') COLLATE "C" !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_REF' USING ERRCODE='22023';
 END IF;
 RETURN jsonb_build_object('assetType',t,'assetId',i,'revision',r,'contentHash',h);
END $body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.original_source_ref(jsonb,text) FROM PUBLIC;
ALTER FUNCTION aos_capacity_publication_private.original_source_ref(jsonb,text) OWNER TO aos_capacity_publication_owner;

CREATE FUNCTION aos_capacity_publication_private.original_source_time(p jsonb)
RETURNS TABLE(instant timestamptz,canonical text) LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER
SET search_path=pg_catalog AS $body$
DECLARE s text; parts text[]; local_time timestamp; offset_minutes integer; suffix text; n double precision;
BEGIN
 IF jsonb_typeof(p) NOT IN('string','number') THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_TIME' USING ERRCODE='22023';
 END IF;
 s:=p#>>'{}';
 IF s COLLATE "C" ~ '^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$' THEN
  n:=s::double precision;
  -- Original datetime parser distinguishes fractional JSON numbers at this
  -- positive threshold from numeric strings; preserve that accepted domain.
  IF jsonb_typeof(p)='number' AND n>20000000000 AND floor(n)=20000000000 THEN
   instant:=to_timestamp(floor(n))+(round((n-floor(n))*1000)*interval '1 microsecond');
  ELSE
   IF abs(n)>20000000000 THEN n:=n/1000; END IF;
   instant:=to_timestamp(n);
  END IF;
  local_time:=instant AT TIME ZONE 'UTC';
  IF extract(year FROM local_time) NOT BETWEEN 1 AND 9999 THEN
   RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_TIME' USING ERRCODE='22023';
  END IF;
  suffix:='Z';
 ELSE
  IF jsonb_typeof(p)<>'string' THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_TIME' USING ERRCODE='22023'; END IF;
  parts:=regexp_match(s COLLATE "C",'^([0-9]{4}-[0-9]{2}-[0-9]{2})[Tt ]([0-9]{2}):([0-9]{2})(:([0-9]{2})([.,]([0-9]+))?)?([Zz]|([+-])([0-9]{2}):?([0-9]{2}))$');
  IF parts IS NULL OR parts[2]::integer>23 OR parts[3]::integer>59 OR COALESCE(parts[5],'0')::integer>59 THEN
   RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_TIME' USING ERRCODE='22023';
  END IF;
  local_time:=(parts[1]||' '||parts[2]||':'||parts[3]||':'||COALESCE(parts[5],'00')||
    CASE WHEN parts[7] IS NULL THEN '' ELSE '.'||left(parts[7],6) END)::timestamp;
  IF lower(parts[8])='z' THEN offset_minutes:=0;
  ELSE
   IF parts[10]::integer>23 OR parts[11]::integer>59 THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_TIME' USING ERRCODE='22023'; END IF;
   offset_minutes:=(parts[10]::integer*60+parts[11]::integer)*CASE WHEN parts[9]='-' THEN -1 ELSE 1 END;
  END IF;
  instant:=(local_time-offset_minutes*interval '1 minute') AT TIME ZONE 'UTC';
  suffix:=CASE WHEN offset_minutes=0 THEN 'Z' ELSE parts[9]||parts[10]||':'||parts[11] END;
 END IF;
 canonical:=to_char(local_time,'YYYY-MM-DD"T"HH24:MI:SS')||
   CASE WHEN to_char(local_time,'US')='000000' THEN '' ELSE '.'||to_char(local_time,'US') END||suffix;
 RETURN NEXT;
EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_TIME' USING ERRCODE='22023';
END $body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.original_source_time(jsonb) FROM PUBLIC;
ALTER FUNCTION aos_capacity_publication_private.original_source_time(jsonb) OWNER TO aos_capacity_publication_owner;

CREATE FUNCTION aos_capacity_publication_private.read_original_source_candidate(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE tenant jsonb; version jsonb; account jsonb; basis jsonb; request jsonb; approval jsonb;
 allowed jsonb; start_time timestamptz; end_time timestamptz; start_text text; end_text text;
BEGIN
 IF jsonb_typeof(p)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(p))<>9 OR p-ARRAY[
   'schemaVersion','schema_version','tenant','physicalAccountRef','physical_account_ref','basisRef','basis_ref',
   'allocationRequestRef','allocation_request_ref','allocationApprovalRef','allocation_approval_ref',
   'validFrom','valid_from','validUntil','valid_until','executionAllowed','execution_allowed']<>'{}'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_CANDIDATE' USING ERRCODE='22023';
 END IF;
 version:=aos_capacity_publication_private.original_source_field(p,'schemaVersion','schema_version');
 tenant:=aos_capacity_publication_private.original_source_field(p,'tenant','tenant');
 allowed:=aos_capacity_publication_private.original_source_field(p,'executionAllowed','execution_allowed');
 IF jsonb_typeof(version)<>'number' OR version#>>'{}'<>'1' OR allowed<>'false'::jsonb
   OR jsonb_typeof(tenant)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(tenant))<>2
   OR tenant-ARRAY['orgId','org_id','projectId','project_id']<>'{}'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_CANDIDATE' USING ERRCODE='22023';
 END IF;
 tenant:=jsonb_build_object('orgId',aos_capacity_publication_private.original_source_field(tenant,'orgId','org_id'),
   'projectId',aos_capacity_publication_private.original_source_field(tenant,'projectId','project_id'));
 IF tenant<>jsonb_build_object('orgId','org-org','projectId','dev-project') THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_CANDIDATE' USING ERRCODE='22023';
 END IF;
 account:=aos_capacity_publication_private.original_source_ref(aos_capacity_publication_private.original_source_field(p,'physicalAccountRef','physical_account_ref'),'ProviderPhysicalAccountCandidateRevision');
 basis:=aos_capacity_publication_private.original_source_ref(aos_capacity_publication_private.original_source_field(p,'basisRef','basis_ref'),'ProviderCapacityBasisCandidateRevision');
 request:=aos_capacity_publication_private.original_source_ref(aos_capacity_publication_private.original_source_field(p,'allocationRequestRef','allocation_request_ref'),'ProviderCapacityRequest');
 approval:=aos_capacity_publication_private.original_source_ref(aos_capacity_publication_private.original_source_field(p,'allocationApprovalRef','allocation_approval_ref'),'ActionApprovalEvent');
 IF request->>'revision'<>'1' OR approval->>'revision'<>'1' THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_CANDIDATE' USING ERRCODE='22023'; END IF;
 SELECT instant,canonical INTO start_time,start_text FROM aos_capacity_publication_private.original_source_time(aos_capacity_publication_private.original_source_field(p,'validFrom','valid_from'));
 SELECT instant,canonical INTO end_time,end_text FROM aos_capacity_publication_private.original_source_time(aos_capacity_publication_private.original_source_field(p,'validUntil','valid_until'));
 IF start_time>=end_time OR end_time-start_time>interval '366 days' THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_SOURCE_CANDIDATE' USING ERRCODE='22023'; END IF;
 RETURN jsonb_build_object('schemaVersion',version,'tenant',tenant,'physicalAccountRef',account,'basisRef',basis,
  'allocationRequestRef',request,'allocationApprovalRef',approval,'validFrom',start_text,'validUntil',end_text,'executionAllowed',false);
END $body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_original_source_candidate(jsonb) FROM PUBLIC;
ALTER FUNCTION aos_capacity_publication_private.read_original_source_candidate(jsonb) OWNER TO aos_capacity_publication_owner;
"""

# Complete native entry query; original private Guard still owns the legacy path.
CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL = CAPACITY_APPROVED_SOURCE_ROW_SQL.replace(
    'FOR SHARE OF p', r"""
  AND p.action_binding_hash=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
    public.canonical_asset_registry_jsonb(pg_catalog.jsonb_build_object(
      'sourceCandidate',aos_capacity_publication_private.read_original_source_candidate(p.payload->'sourceCandidate'),
      'actionTypeRevisionHash',p.action_type_snapshot->'revisionHash')),'UTF8')),'hex')
FOR SHARE OF p
""")

# S11 untrusted original application model; not Provider/Evidence authority.
CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_original_capacity_application(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE v jsonb; tenant jsonb; provider jsonb; evidence jsonb; identity text; trims text;
 starts timestamptz; ends timestamptz; expires timestamptz; start_text text; end_text text; expiry_text text;
BEGIN
 IF jsonb_typeof(p)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(p))<>12
  OR p-ARRAY['schemaVersion','schema_version','tenant','providerRef','provider_ref',
   'physicalAccountId','physical_account_id','requestedMaxConcurrency','requested_max_concurrency',
   'requestedMaxTokenUnits','requested_max_token_units','tokenUnit','token_unit','basisKind','basis_kind',
   'basisEvidenceRef','basis_evidence_ref','validFrom','valid_from','validUntil','valid_until',
   'proposalExpiresAt','proposal_expires_at']<>'{}'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPLICATION' USING ERRCODE='22023';
 END IF;
 v:=jsonb_build_object(
  'schemaVersion',aos_capacity_publication_private.original_source_field(p,'schemaVersion','schema_version'),
  'tenant',aos_capacity_publication_private.original_source_field(p,'tenant','tenant'),
  'providerRef',aos_capacity_publication_private.original_source_field(p,'providerRef','provider_ref'),
  'physicalAccountId',aos_capacity_publication_private.original_source_field(p,'physicalAccountId','physical_account_id'),
  'requestedMaxConcurrency',aos_capacity_publication_private.original_source_field(p,'requestedMaxConcurrency','requested_max_concurrency'),
  'requestedMaxTokenUnits',aos_capacity_publication_private.original_source_field(p,'requestedMaxTokenUnits','requested_max_token_units'),
  'tokenUnit',aos_capacity_publication_private.original_source_field(p,'tokenUnit','token_unit'),
  'basisKind',aos_capacity_publication_private.original_source_field(p,'basisKind','basis_kind'),
  'basisEvidenceRef',aos_capacity_publication_private.original_source_field(p,'basisEvidenceRef','basis_evidence_ref'),
  'validFrom',aos_capacity_publication_private.original_source_field(p,'validFrom','valid_from'),
  'validUntil',aos_capacity_publication_private.original_source_field(p,'validUntil','valid_until'),
  'proposalExpiresAt',aos_capacity_publication_private.original_source_field(p,'proposalExpiresAt','proposal_expires_at'));
 tenant:=v->'tenant';
 IF jsonb_typeof(v->'schemaVersion')<>'number' OR v->>'schemaVersion'<>'1'
  OR v->'tokenUnit'<>'"token"'::jsonb OR v->'basisKind'<>'"owner_requested_allocation"'::jsonb
  OR jsonb_typeof(tenant)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(tenant))<>2
  OR tenant-ARRAY['orgId','org_id','projectId','project_id']<>'{}'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPLICATION' USING ERRCODE='22023';
 END IF;
 tenant:=jsonb_build_object('orgId',aos_capacity_publication_private.original_source_field(tenant,'orgId','org_id'),
   'projectId',aos_capacity_publication_private.original_source_field(tenant,'projectId','project_id'));
 IF tenant<>jsonb_build_object('orgId','org-org','projectId','dev-project') THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPLICATION' USING ERRCODE='22023';
 END IF;
 identity:=v->>'physicalAccountId';
 SELECT string_agg(chr(point),'') INTO trims FROM unnest(ARRAY[9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288]) point;
 IF jsonb_typeof(v->'physicalAccountId')<>'string' OR length(identity) NOT BETWEEN 1 AND 200
  OR identity<>btrim(identity,trims)
  OR jsonb_typeof(v->'requestedMaxConcurrency')<>'number'
  OR (v->>'requestedMaxConcurrency') COLLATE "C" !~ '^[1-9][0-9]*$'
  OR jsonb_typeof(v->'requestedMaxTokenUnits')<>'number'
  OR (v->>'requestedMaxTokenUnits') COLLATE "C" !~ '^[1-9][0-9]*$' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPLICATION' USING ERRCODE='22023';
 END IF;
 IF (v->>'requestedMaxConcurrency')::numeric NOT BETWEEN 1 AND 1000000
  OR (v->>'requestedMaxTokenUnits')::numeric NOT BETWEEN 1 AND 1000000000000 THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPLICATION' USING ERRCODE='22023';
 END IF;
 provider:=aos_capacity_publication_private.original_source_ref(v->'providerRef','ProviderInstanceRevision');
 evidence:=aos_capacity_publication_private.original_source_ref(v->'basisEvidenceRef','EvidenceBundleRevision');
 SELECT instant,canonical INTO starts,start_text FROM aos_capacity_publication_private.original_source_time(v->'validFrom');
 SELECT instant,canonical INTO ends,end_text FROM aos_capacity_publication_private.original_source_time(v->'validUntil');
 SELECT instant,canonical INTO expires,expiry_text FROM aos_capacity_publication_private.original_source_time(v->'proposalExpiresAt');
 IF NOT starts<expires OR expires>ends OR ends-starts>interval '366 days' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPLICATION' USING ERRCODE='22023';
 END IF;
 RETURN v||jsonb_build_object('tenant',tenant,'providerRef',provider,'basisEvidenceRef',evidence,
   'validFrom',start_text,'validUntil',end_text,'proposalExpiresAt',expiry_text);
EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPLICATION' USING ERRCODE='22023';
END $body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_original_capacity_application(jsonb) FROM PUBLIC;
ALTER FUNCTION aos_capacity_publication_private.read_original_capacity_application(jsonb) OWNER TO aos_capacity_publication_owner;
"""

# Full native publication only: original raw hash stays authoritative.
CAPACITY_NATIVE_REQUEST_ROW_SQL = 'WITH original AS ('+CAPACITY_REQUEST_ROW_SQL+r"""), typed AS (
 SELECT r.*,aos_capacity_publication_private.read_original_capacity_application(r.request_json->'application') AS normalized_application
 FROM original r WHERE r.created_by=%(maker)s
) SELECT * FROM typed
WHERE expires_at=(normalized_application->>'proposalExpiresAt')::timestamptz
  AND (normalized_application->>'validFrom')::timestamptz<=pg_catalog.clock_timestamp()
  AND pg_catalog.clock_timestamp()<(normalized_application->>'proposalExpiresAt')::timestamptz
"""

# Fixed original candidate models. Returned normalized claims remain untrusted.
CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.original_claim_fields(p jsonb,names jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE result jsonb:='{}'::jsonb; name text; alias text; allowed text[];
BEGIN
 IF jsonb_typeof(p)<>'object' OR jsonb_typeof(names)<>'object'
  OR (SELECT count(*) FROM jsonb_object_keys(p))<>(SELECT count(*) FROM jsonb_object_keys(names)) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_CLAIM_FIELDS' USING ERRCODE='22023';
 END IF;
 SELECT array_agg(value) INTO allowed FROM (
  SELECT key AS value FROM jsonb_each_text(names) UNION SELECT value FROM jsonb_each_text(names)) fields;
 IF p-allowed<>'{}'::jsonb THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_CLAIM_FIELDS' USING ERRCODE='22023'; END IF;
 FOR name,alias IN SELECT key,value FROM jsonb_each_text(names) LOOP
  result:=result||jsonb_build_object(name,aos_capacity_publication_private.original_source_field(p,name,alias));
 END LOOP;
 RETURN result;
END $body$;
CREATE FUNCTION aos_capacity_publication_private.original_claim_header(v jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE tenant jsonb;
BEGIN
 IF jsonb_typeof(v->'schemaVersion')<>'number' OR v->>'schemaVersion'<>'1' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_CLAIM_HEADER' USING ERRCODE='22023';
 END IF;
 tenant:=aos_capacity_publication_private.original_claim_fields(v->'tenant','{"orgId":"org_id","projectId":"project_id"}'::jsonb);
 IF tenant<>jsonb_build_object('orgId','org-org','projectId','dev-project') THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_CLAIM_HEADER' USING ERRCODE='22023';
 END IF;
 RETURN v||jsonb_build_object('tenant',tenant);
END $body$;
CREATE FUNCTION aos_capacity_publication_private.original_claim_identity(p jsonb)
RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE value text:=p#>>'{}'; trims text;
BEGIN
 SELECT string_agg(chr(point),'') INTO trims FROM unnest(ARRAY[9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288]) point;
 IF jsonb_typeof(p)<>'string' OR length(value) NOT BETWEEN 1 AND 200 OR value<>btrim(value,trims) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_CLAIM_IDENTITY' USING ERRCODE='22023';
 END IF;
 RETURN value;
END $body$;
CREATE FUNCTION aos_capacity_publication_private.original_claim_integer(p jsonb,ceiling bigint)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
BEGIN
 IF jsonb_typeof(p)<>'number' OR (p#>>'{}') COLLATE "C" !~ '^[1-9][0-9]*$' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_CLAIM_INTEGER' USING ERRCODE='22023';
 END IF;
 IF (p#>>'{}')::numeric>ceiling THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_CLAIM_INTEGER' USING ERRCODE='22023'; END IF;
 RETURN p;
END $body$;
CREATE FUNCTION aos_capacity_publication_private.read_original_token_limit(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE names jsonb; v jsonb; time_text text;
BEGIN
 names:='{"mode":"mode","unit":"unit","maxTokens":"max_tokens"}'::jsonb;
 IF p->'mode'='"fixed_window_rate"'::jsonb THEN
  names:=names||'{"windowSeconds":"window_seconds","windowAnchor":"window_anchor"}'::jsonb;
 ELSIF p->'mode' IS DISTINCT FROM '"inflight_upper_bound"'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_TOKEN_LIMIT' USING ERRCODE='22023';
 END IF;
 v:=aos_capacity_publication_private.original_claim_fields(p,names);
 IF v->'unit'<>'"token"'::jsonb THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_TOKEN_LIMIT' USING ERRCODE='22023'; END IF;
 PERFORM aos_capacity_publication_private.original_claim_integer(v->'maxTokens',1000000000000);
 IF v->'mode'='"fixed_window_rate"'::jsonb THEN
  PERFORM aos_capacity_publication_private.original_claim_integer(v->'windowSeconds',86400);
  SELECT canonical INTO time_text FROM aos_capacity_publication_private.original_source_time(v->'windowAnchor');
  v:=v||jsonb_build_object('windowAnchor',time_text);
 END IF;
 RETURN v;
END $body$;
CREATE FUNCTION aos_capacity_publication_private.read_original_physical_account(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE v jsonb; refs jsonb:='[]'::jsonb; element jsonb; normalized jsonb; ids text[]:='{}'::text[]; evidence jsonb;
BEGIN
 v:=aos_capacity_publication_private.original_claim_header(aos_capacity_publication_private.original_claim_fields(p,
  '{"schemaVersion":"schema_version","tenant":"tenant","physicalAccountId":"physical_account_id","supplierId":"supplier_id","supplierAccountFingerprint":"supplier_account_fingerprint","providerRefs":"provider_refs","evidenceRef":"evidence_ref"}'::jsonb));
 PERFORM aos_capacity_publication_private.original_claim_identity(v->'physicalAccountId');
 PERFORM aos_capacity_publication_private.original_claim_identity(v->'supplierId');
 IF jsonb_typeof(v->'supplierAccountFingerprint')<>'string'
  OR (v->>'supplierAccountFingerprint') COLLATE "C" !~ '^[0-9a-f]{64}$'
  OR jsonb_typeof(v->'providerRefs')<>'array' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_ACCOUNT' USING ERRCODE='22023';
 END IF;
 IF jsonb_array_length(v->'providerRefs') NOT BETWEEN 1 AND 1000 THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_ACCOUNT' USING ERRCODE='22023';
 END IF;
 FOR element IN SELECT value FROM jsonb_array_elements(v->'providerRefs') LOOP
  normalized:=aos_capacity_publication_private.original_source_ref(element,'ProviderInstanceRevision');
  IF normalized->>'assetId'=ANY(ids) THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_ACCOUNT' USING ERRCODE='22023'; END IF;
  ids:=array_append(ids,normalized->>'assetId'); refs:=refs||jsonb_build_array(normalized);
 END LOOP;
 evidence:=aos_capacity_publication_private.original_source_ref(v->'evidenceRef','EvidenceBundleRevision');
 RETURN v||jsonb_build_object('providerRefs',refs,'evidenceRef',evidence);
EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_ACCOUNT' USING ERRCODE='22023';
END $body$;
CREATE FUNCTION aos_capacity_publication_private.read_original_capacity_basis(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE v jsonb; account jsonb; evidence jsonb; tokens jsonb;
 starts timestamptz; ends timestamptz; observed timestamptz; start_text text; end_text text; observation_text text;
BEGIN
 v:=aos_capacity_publication_private.original_claim_header(aos_capacity_publication_private.original_claim_fields(p,
  '{"schemaVersion":"schema_version","tenant":"tenant","basisKind":"basis_kind","physicalAccountRef":"physical_account_ref","evidenceRef":"evidence_ref","maxConcurrency":"max_concurrency","tokenLimit":"token_limit","observedAt":"observed_at","validFrom":"valid_from","validUntil":"valid_until"}'::jsonb));
 IF v->'basisKind' NOT IN ('"owner_allocation"'::jsonb,'"supplier_limit_claim"'::jsonb) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_BASIS' USING ERRCODE='22023';
 END IF;
 account:=aos_capacity_publication_private.original_source_ref(v->'physicalAccountRef','ProviderPhysicalAccountCandidateRevision');
 evidence:=aos_capacity_publication_private.original_source_ref(v->'evidenceRef','EvidenceBundleRevision');
 PERFORM aos_capacity_publication_private.original_claim_integer(v->'maxConcurrency',1000000);
 tokens:=aos_capacity_publication_private.read_original_token_limit(v->'tokenLimit');
 SELECT instant,canonical INTO starts,start_text FROM aos_capacity_publication_private.original_source_time(v->'validFrom');
 SELECT instant,canonical INTO ends,end_text FROM aos_capacity_publication_private.original_source_time(v->'validUntil');
 SELECT instant,canonical INTO observed,observation_text FROM aos_capacity_publication_private.original_source_time(v->'observedAt');
 IF starts>=ends OR ends-starts>interval '366 days' OR observed>ends THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_BASIS' USING ERRCODE='22023';
 END IF;
 RETURN v||jsonb_build_object('physicalAccountRef',account,'evidenceRef',evidence,'tokenLimit',tokens,
  'validFrom',start_text,'validUntil',end_text,'observedAt',observation_text);
EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_BASIS' USING ERRCODE='22023';
END $body$;
""" + '\n'.join(
    f'REVOKE ALL ON FUNCTION aos_capacity_publication_private.{signature} FROM PUBLIC;\n'
    f'ALTER FUNCTION aos_capacity_publication_private.{signature} OWNER TO aos_capacity_publication_owner;'
    for signature in ('original_claim_fields(jsonb,jsonb)','original_claim_header(jsonb)',
        'original_claim_identity(jsonb)','original_claim_integer(jsonb,bigint)',
        'read_original_token_limit(jsonb)','read_original_physical_account(jsonb)',
        'read_original_capacity_basis(jsonb)'))

CAPACITY_NATIVE_CANDIDATE_ROW_SQL = 'WITH original AS ('+CAPACITY_CANDIDATE_ROW_SQL+r"""), typed AS (
 SELECT c.*,CASE c.candidate_kind
  WHEN 'account' THEN aos_capacity_publication_private.read_original_physical_account(c.request_json->'candidate')
  WHEN 'basis' THEN aos_capacity_publication_private.read_original_capacity_basis(c.request_json->'candidate')
 END AS normalized_candidate FROM original c
) SELECT * FROM typed WHERE normalized_candidate IS NOT NULL
"""

CAPACITY_NATIVE_SOURCE_COMBINATION_SQL = (
    'WITH request AS ('+CAPACITY_NATIVE_REQUEST_ROW_SQL+'), account AS ('+
    _combination_candidate_sql('account',statement=CAPACITY_NATIVE_CANDIDATE_ROW_SQL)+'), basis AS ('+
    _combination_candidate_sql('basis',statement=CAPACITY_NATIVE_CANDIDATE_ROW_SQL)+r"""), terms AS (
      SELECT a.candidate_id,a.revision,a.content_hash,
        a.normalized_candidate AS account,b.normalized_candidate AS basis,
        r.normalized_application AS application
      FROM account a CROSS JOIN basis b CROSS JOIN request r
    ) SELECT 1 AS matched FROM terms
    WHERE basis->'physicalAccountRef'=pg_catalog.jsonb_build_object(
      'assetType','ProviderPhysicalAccountCandidateRevision','assetId',candidate_id,
      'revision',revision,'contentHash',content_hash)
      AND account->'physicalAccountId'=application->'physicalAccountId'
      AND EXISTS(SELECT 1 FROM pg_catalog.jsonb_array_elements(account->'providerRefs') AS refs(value)
                 WHERE value=application->'providerRef')
      AND (basis->>'maxConcurrency')::numeric<=(application->>'requestedMaxConcurrency')::numeric
""")

# Provider uses the original coercive runtime model, not strict capacity DTOs.
CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.original_provider_string(p jsonb,maximum integer,strip boolean)
RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE value text:=p#>>'{}'; trims text;
BEGIN
 IF jsonb_typeof(p)<>'string' OR length(value) NOT BETWEEN 1 AND maximum THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_STRING' USING ERRCODE='22023';
 END IF;
 IF strip THEN
  SELECT string_agg(chr(point),'') INTO trims FROM unnest(ARRAY[9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288]) point;
  value:=btrim(value,trims);
  IF value='' THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_STRING' USING ERRCODE='22023'; END IF;
 END IF;
 RETURN value;
END $body$;
CREATE FUNCTION aos_capacity_publication_private.original_provider_integer(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE value text:=p#>>'{}'; number numeric; trims text; bits bytea; exponent integer;
 mantissa numeric; point integer; digits text;
BEGIN
 IF jsonb_typeof(p)='boolean' THEN RETURN CASE WHEN p='true'::jsonb THEN '1'::jsonb ELSE '0'::jsonb END;
 ELSIF jsonb_typeof(p)='number' THEN
  IF position('.' IN value)>0 THEN
   -- Original JSON reader decodes decimal literals as binary64 floats.
   -- Reconstruct their exact integer instead of rounded float text/numeric.
   bits:=float8send(value::double precision);
   exponent:=((get_byte(bits,0)&127)<<4)+(get_byte(bits,1)>>4);
   IF exponent=2047 THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_INTEGER' USING ERRCODE='22023'; END IF;
   mantissa:=(get_byte(bits,1)&15)::numeric;
   FOR point IN 2..7 LOOP mantissa:=mantissa*256+get_byte(bits,point); END LOOP;
   IF exponent>0 THEN mantissa:=mantissa+4503599627370496; ELSE exponent:=1; END IF;
   IF exponent<1075 THEN
    number:=power(2::numeric,1075-exponent);
    IF mod(mantissa,number)<>0 THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_INTEGER' USING ERRCODE='22023'; END IF;
    number:=mantissa/number;
   ELSE number:=mantissa*power(2::numeric,exponent-1075); END IF;
   IF (get_byte(bits,0)&128)<>0 THEN number:=-number; END IF;
  ELSE number:=value::numeric; END IF;
 ELSIF jsonb_typeof(p)='string' THEN
  -- Rust integer parsing omits U+001C..U+001F from its whitespace set.
  SELECT string_agg(chr(code),'') INTO trims FROM unnest(ARRAY[9,10,11,12,13,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288]) code;
  value:=btrim(value,trims);
  IF value COLLATE "C" !~ '^[+-]?[0-9](_?[0-9])*(\.0+)?$' THEN
   RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_INTEGER' USING ERRCODE='22023';
  END IF;
  digits:=ltrim(split_part(replace(value,'_',''),'.',1),'+-0');
  IF length(digits)>4300 THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_INTEGER' USING ERRCODE='22023'; END IF;
  number:=replace(value,'_','')::numeric;
 ELSE RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_INTEGER' USING ERRCODE='22023'; END IF;
 IF number<>trunc(number) THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_INTEGER' USING ERRCODE='22023'; END IF;
 RETURN to_jsonb(trunc(number));
END $body$;
CREATE FUNCTION aos_capacity_publication_private.original_provider_ref(p jsonb,kind text)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE v jsonb; asset_type text; asset_id text; revision jsonb; hash text;
BEGIN
 v:=aos_capacity_publication_private.original_claim_fields(p,'{"assetType":"asset_type","assetId":"asset_id","revision":"revision","contentHash":"content_hash"}'::jsonb);
 asset_type:=aos_capacity_publication_private.original_provider_string(v->'assetType',80,true);
 asset_id:=aos_capacity_publication_private.original_provider_string(v->'assetId',200,true);
 revision:=aos_capacity_publication_private.original_provider_integer(v->'revision');
 hash:=aos_capacity_publication_private.original_provider_string(v->'contentHash',64,false);
 IF asset_type<>kind OR (revision#>>'{}')::numeric<1 OR hash COLLATE "C" !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_REF' USING ERRCODE='22023';
 END IF;
 RETURN jsonb_build_object('assetType',asset_type,'assetId',asset_id,'revision',revision,'contentHash',hash);
END $body$;
CREATE FUNCTION aos_capacity_publication_private.original_provider_time(p jsonb)
RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE value text:=p#>>'{}'; canonical text; naive boolean:=false;
BEGIN
 IF jsonb_typeof(p)='string' THEN
  IF value COLLATE "C" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
   value:=value||'T00:00:00Z';naive:=true;
  ELSIF value COLLATE "C" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt ][0-9]{2}:[0-9]{2}(:[0-9]{2}([.,][0-9]+)?)?$' THEN
   value:=value||'Z';naive:=true;
  END IF;
 END IF;
 SELECT t.canonical INTO canonical FROM aos_capacity_publication_private.original_source_time(
  CASE WHEN naive THEN to_jsonb(value) ELSE p END) t;
 RETURN CASE WHEN naive THEN left(canonical,length(canonical)-1) ELSE canonical END;
END $body$;
CREATE FUNCTION aos_capacity_publication_private.read_original_provider(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE v jsonb; tenant jsonb; endpoint jsonb; metadata jsonb; timeout jsonb; revision jsonb;
 identifier text; hash text; secret text; version text; actor text; created text; lifecycle text;
 plugin jsonb; egress jsonb; classification jsonb;
BEGIN
 v:=aos_capacity_publication_private.original_claim_fields(p,
  '{"tenant":"tenant","providerInstanceId":"provider_instance_id","revision":"revision","contentHash":"content_hash","pluginRef":"plugin_ref","endpointProfile":"endpoint_profile","secretRef":"secret_ref","secretVersion":"secret_version","egressPolicyRef":"egress_policy_ref","dataClassificationPolicyRef":"data_classification_policy_ref","lifecycle":"lifecycle","createdBy":"created_by","createdAt":"created_at"}'::jsonb);
 tenant:=aos_capacity_publication_private.original_claim_fields(v->'tenant','{"orgId":"org_id","projectId":"project_id"}'::jsonb);
 IF jsonb_typeof(tenant->'orgId')<>'string' OR jsonb_typeof(tenant->'projectId')<>'string' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_TENANT' USING ERRCODE='22023';
 END IF;
 identifier:=aos_capacity_publication_private.original_provider_string(v->'providerInstanceId',200,false);
 revision:=aos_capacity_publication_private.original_provider_integer(v->'revision');
 hash:=aos_capacity_publication_private.original_provider_string(v->'contentHash',64,false);
 IF (revision#>>'{}')::numeric<1 OR hash COLLATE "C" !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER' USING ERRCODE='22023';
 END IF;
 plugin:=aos_capacity_publication_private.original_provider_ref(v->'pluginRef','ProviderPluginRevision');
 egress:=aos_capacity_publication_private.original_provider_ref(v->'egressPolicyRef','EgressPolicyRevision');
 classification:=aos_capacity_publication_private.original_provider_ref(v->'dataClassificationPolicyRef','DataClassificationPolicyRevision');
 endpoint:=v->'endpointProfile';
 IF jsonb_typeof(endpoint)<>'object' THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_ENDPOINT' USING ERRCODE='22023'; END IF;
 IF NOT endpoint?'metadata' THEN endpoint:=endpoint||'{"metadata":{}}'::jsonb; END IF;
 endpoint:=aos_capacity_publication_private.original_claim_fields(endpoint,'{"baseUrl":"base_url","region":"region","timeoutMs":"timeout_ms","metadata":"metadata"}'::jsonb);
 PERFORM aos_capacity_publication_private.original_provider_string(endpoint->'baseUrl',1024,false);
 PERFORM aos_capacity_publication_private.original_provider_string(endpoint->'region',120,false);
 timeout:=aos_capacity_publication_private.original_provider_integer(endpoint->'timeoutMs');
 IF (timeout#>>'{}')::numeric NOT BETWEEN 100 AND 3600000 THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_ENDPOINT' USING ERRCODE='22023';
 END IF;
 metadata:=endpoint->'metadata';
 IF jsonb_typeof(metadata)<>'object' THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_ENDPOINT' USING ERRCODE='22023'; END IF;
 IF (SELECT count(*) FROM jsonb_object_keys(metadata))>32
  OR EXISTS(SELECT 1 FROM jsonb_each(metadata) WHERE jsonb_typeof(value)<>'string') THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_ENDPOINT' USING ERRCODE='22023';
 END IF;
 endpoint:=endpoint||jsonb_build_object('timeoutMs',timeout);
 secret:=aos_capacity_publication_private.original_provider_string(v->'secretRef',512,true);
 IF NOT (secret LIKE 'vault://%' OR secret LIKE 'secret://%' OR secret LIKE 'keychain://%') THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_SECRET_REF' USING ERRCODE='22023';
 END IF;
 version:=aos_capacity_publication_private.original_provider_string(v->'secretVersion',120,false);
 actor:=aos_capacity_publication_private.original_provider_string(v->'createdBy',200,false);
 lifecycle:=aos_capacity_publication_private.original_provider_string(v->'lifecycle',30,false);
 IF lifecycle NOT IN ('draft','validated','active','suspended','revoked') THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER_LIFECYCLE' USING ERRCODE='22023';
 END IF;
 created:=aos_capacity_publication_private.original_provider_time(v->'createdAt');
 RETURN v||jsonb_build_object('tenant',tenant,'providerInstanceId',identifier,'revision',revision,'contentHash',hash,
  'pluginRef',plugin,'egressPolicyRef',egress,'dataClassificationPolicyRef',classification,
  'endpointProfile',endpoint,'secretRef',secret,'secretVersion',version,'createdBy',actor,'createdAt',created);
EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_PROVIDER' USING ERRCODE='22023';
END $body$;
""" + '\n'.join(
    f'REVOKE ALL ON FUNCTION aos_capacity_publication_private.{signature} FROM PUBLIC;\n'
    f'ALTER FUNCTION aos_capacity_publication_private.{signature} OWNER TO aos_capacity_publication_owner;'
    for signature in ('original_provider_string(jsonb,integer,boolean)','original_provider_integer(jsonb)',
        'original_provider_ref(jsonb,text)','original_provider_time(jsonb)','read_original_provider(jsonb)'))

CAPACITY_NATIVE_PROVIDER_ROW_SQL = r"""
WITH original AS (
 SELECT r.provider_instance_id,r.revision,r.content_hash,r.lifecycle,r.payload
 FROM public.aip_provider_instance_head h JOIN public.aip_provider_instance_revision r
 ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.provider_instance_id=h.provider_instance_id
 AND r.revision=h.current_revision
 WHERE h.org_id=%(org_id)s AND h.project_id=%(project_id)s AND h.provider_instance_id=%(provider_id)s
 FOR SHARE OF h
), typed AS (
 SELECT r.*,aos_capacity_publication_private.read_original_provider(r.payload) AS normalized_provider FROM original r
) SELECT * FROM typed
WHERE provider_instance_id=%(provider_id)s AND revision=%(revision)s AND content_hash=%(content_hash)s AND lifecycle='active'
 AND normalized_provider->'tenant'=pg_catalog.jsonb_build_object('orgId',%(org_id)s::text,'projectId',%(project_id)s::text)
 AND normalized_provider->>'providerInstanceId'=provider_instance_id
 AND (normalized_provider->>'revision')::numeric=revision
 AND normalized_provider->>'contentHash'=content_hash AND normalized_provider->>'lifecycle'=lifecycle
 AND pg_catalog.encode(public.digest(pg_catalog.convert_to(public.canonical_asset_registry_jsonb(
  normalized_provider-ARRAY['tenant','revision','contentHash','createdBy','createdAt']),'UTF8'),'sha256'),'hex')=content_hash
"""

# Original Build input shape only; provenance/receipt/hash authority is checked
# separately by the complete native Source transaction, never by this reader.
CAPACITY_ORIGINAL_BUILD_PROFILE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.original_build_exact_ref(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE v jsonb; revision text; hash text;
BEGIN
 v:=aos_capacity_publication_private.original_claim_fields(p,
  '{"resourceType":"resourceType","resourceId":"resourceId","revision":"revision","contentHash":"contentHash"}'::jsonb);
 PERFORM aos_capacity_publication_private.original_provider_string(v->'resourceType',80,false);
 PERFORM aos_capacity_publication_private.original_provider_string(v->'resourceId',200,false);
 revision:=v->>'revision'; hash:=v->>'contentHash';
 -- A coercible non-integer representation changes the original model's
 -- canonical serialization, so it is not an accepted Build provenance input.
 IF jsonb_typeof(v->'revision')<>'number' OR revision COLLATE "C" !~ '^[0-9]+$'
  OR revision::numeric<1 OR jsonb_typeof(v->'contentHash')<>'string'
  OR hash COLLATE "C" !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_BUILD_REF' USING ERRCODE='22023';
 END IF;
 RETURN v;
END $body$;
CREATE FUNCTION aos_capacity_publication_private.original_build_resource_ref(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE v jsonb; field text; value text;
BEGIN
 v:=aos_capacity_publication_private.original_claim_fields(p,
  '{"resourceType":"resourceType","resourceId":"resourceId","revision":"revision","authority":"authority"}'::jsonb);
 FOREACH field IN ARRAY ARRAY['resourceType','resourceId','authority'] LOOP
  value:=aos_capacity_publication_private.original_provider_string(v->field,2147483647,true);
  IF value IS DISTINCT FROM v->>field THEN
   RAISE EXCEPTION 'CAPACITY_ORIGINAL_BUILD_RESOURCE_REF' USING ERRCODE='22023';
  END IF;
 END LOOP;
 IF jsonb_typeof(v->'revision') NOT IN ('string','null') THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_BUILD_RESOURCE_REF' USING ERRCODE='22023';
 END IF;
 RETURN v;
END $body$;
CREATE FUNCTION aos_capacity_publication_private.read_original_build_request(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE v jsonb; field text; item jsonb; value text; values_seen text[]; cutoff text;
BEGIN
 v:=aos_capacity_publication_private.original_claim_fields(p,
  '{"briefRef":"briefRef","subjectRefs":"subjectRefs","cutoffAt":"cutoffAt","itemRefs":"itemRefs","requiredFactIds":"requiredFactIds","marking":"marking","licenseSummary":"licenseSummary"}'::jsonb);
 PERFORM aos_capacity_publication_private.original_build_exact_ref(v->'briefRef');
 FOREACH field IN ARRAY ARRAY['subjectRefs','itemRefs','requiredFactIds','marking'] LOOP
  IF jsonb_typeof(v->field)<>'array' THEN
   RAISE EXCEPTION 'CAPACITY_ORIGINAL_BUILD_ARRAY' USING ERRCODE='22023';
  END IF;
 END LOOP;
 IF jsonb_array_length(v->'itemRefs')<1 OR jsonb_array_length(v->'requiredFactIds')<1
  OR jsonb_typeof(v->'licenseSummary')<>'object' OR jsonb_typeof(v->'cutoffAt')<>'string' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_BUILD' USING ERRCODE='22023';
 END IF;
 FOR item IN SELECT element.value FROM jsonb_array_elements(v->'subjectRefs') AS element(value) LOOP
  PERFORM aos_capacity_publication_private.original_build_resource_ref(item);
 END LOOP;
 FOR item IN SELECT element.value FROM jsonb_array_elements(v->'itemRefs') AS element(value) LOOP
  PERFORM aos_capacity_publication_private.original_build_exact_ref(item);
 END LOOP;
 FOREACH field IN ARRAY ARRAY['requiredFactIds','marking'] LOOP
  values_seen:=ARRAY[]::text[];
  FOR item IN SELECT element.value FROM jsonb_array_elements(v->field) AS element(value) LOOP
   value:=aos_capacity_publication_private.original_provider_string(item,2147483647,true);
   IF value IS DISTINCT FROM item#>>'{}' OR value=ANY(values_seen) THEN
    RAISE EXCEPTION 'CAPACITY_ORIGINAL_BUILD_STRINGS' USING ERRCODE='22023';
   END IF;
   values_seen:=array_append(values_seen,value);
  END LOOP;
 END LOOP;
 cutoff:=aos_capacity_publication_private.original_provider_time(v->'cutoffAt');
 IF cutoff IS DISTINCT FROM v->>'cutoffAt' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_BUILD_CUTOFF' USING ERRCODE='22023';
 END IF;
 RETURN v;
EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION 'CAPACITY_ORIGINAL_BUILD' USING ERRCODE='22023';
END $body$;
""" + '\n'.join(
    f'REVOKE ALL ON FUNCTION aos_capacity_publication_private.{signature} FROM PUBLIC;\n'
    f'ALTER FUNCTION aos_capacity_publication_private.{signature} OWNER TO aos_capacity_publication_owner;'
    for signature in ('original_build_exact_ref(jsonb)','original_build_resource_ref(jsonb)',
                      'read_original_build_request(jsonb)'))

CAPACITY_ORIGINAL_BUILD_JSON_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.original_build_json(p jsonb)
RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER
SET search_path=pg_catalog SET extra_float_digits=3 AS $body$
DECLARE rendered text; exponent integer;
BEGIN
 CASE jsonb_typeof(p)
 WHEN 'object' THEN
  SELECT '{'||coalesce(string_agg(to_jsonb(element.key)::text||':'||
   aos_capacity_publication_private.original_build_json(element.value),',' ORDER BY element.key COLLATE "C"),'')||'}'
  INTO rendered FROM jsonb_each(p) AS element(key,value);
 WHEN 'array' THEN
  SELECT '['||coalesce(string_agg(aos_capacity_publication_private.original_build_json(element.value),
   ',' ORDER BY element.ordinality),'')||']' INTO rendered
  FROM jsonb_array_elements(p) WITH ORDINALITY AS element(value,ordinality);
 WHEN 'number' THEN
  rendered:=p::text;
  -- Match the original driver's JSON decoding: decimal literals become
  -- binary64; integer literals remain arbitrary precision integers.
  IF position('.' IN rendered)>0 THEN
   BEGIN rendered:=(rendered::double precision)::text;
   EXCEPTION WHEN numeric_value_out_of_range THEN
    IF abs(rendered::numeric)<1 THEN
     RETURN CASE WHEN left(rendered,1)='-' THEN '-0.0' ELSE '0.0' END;
    END IF;
    RETURN CASE WHEN left(rendered,1)='-' THEN '-Infinity' ELSE 'Infinity' END;
   END;
   IF position('e' IN rendered)>0 THEN
    exponent:=split_part(rendered,'e',2)::integer;
    -- Python repr uses fixed notation for exponents -4 through 15.
    IF exponent BETWEEN -4 AND 15 THEN rendered:=(rendered::numeric)::text; END IF;
   END IF;
   IF position('.' IN rendered)=0 AND position('e' IN rendered)=0 THEN rendered:=rendered||'.0'; END IF;
  END IF;
 ELSE rendered:=p::text;
 END CASE;
 RETURN rendered;
END $body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.original_build_json(jsonb) FROM PUBLIC;
ALTER FUNCTION aos_capacity_publication_private.original_build_json(jsonb) OWNER TO aos_capacity_publication_owner;
"""
