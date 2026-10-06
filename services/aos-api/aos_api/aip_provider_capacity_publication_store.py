"""Publication SQL prerequisites; no operational publication Store yet.

These pure encoding and untrusted shape checks do not authenticate a
signature/key or grant capacity. Production installation and the
full approval/currentness/mapping/signature/COMMIT boundary remain separate.
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


def _combination_candidate_sql(kind):
    # Only the two fixed original kinds are used, never caller SQL or names.
    statement=CAPACITY_CANDIDATE_ROW_SQL.replace('%(candidate_kind)s',"'"+kind+"'")
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
