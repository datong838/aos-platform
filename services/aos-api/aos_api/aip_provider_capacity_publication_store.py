"""Publication SQL prerequisites; no operational publication Store yet.

These pure encoding functions do not validate a document's business fields,
authenticate a signature/key or grant capacity. Production installation and the
full approval/currentness/mapping/signature/COMMIT boundary remain separate.
"""

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
