
DECLARE
 owner_oid oid; fact_oids oid[]; r record; g record; flags record;
 tables text[] := ARRAY['meta_membership','aip_provider_capacity_request','aip_provider_capacity_candidate',
  'aip_provider_instance_head','aip_provider_instance_revision','aip_evidence_bundle_revision',
  'aip_evidence_bundle_build_provenance','aip_evidence_bundle_revoke_event',
  'aip_production_contract_receipt','aip_action_withdrawal_event','meta_object_type','meta_action_type',
  'aip_action_proposal','aip_action_draft','aip_action_approval_event'];
 locks jsonb := '{"meta_membership":"subject","aip_provider_instance_head":"provider_instance_id","meta_object_type":"id","meta_action_type":"id","aip_action_proposal":"proposal_id"}';
 tenant text := '((org_id = ''org-org''::text) AND (project_id = ''dev-project''::text) AND (org_id = NULLIF(current_setting(''aos.org_id''::text, true), ''''::text)) AND (project_id = NULLIF(current_setting(''aos.project_id''::text, true), ''''::text)))';
 expression text; tab text; n integer;
BEGIN
 SELECT * INTO r FROM pg_roles WHERE rolname='aos_capacity_publication_owner';
 IF NOT FOUND OR r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
  OR r.rolreplication OR r.rolbypassrls OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid)
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 owner_oid:=r.oid;
 IF EXISTS(SELECT 1 FROM pg_default_acl d WHERE d.defaclrole=owner_oid
   OR EXISTS(SELECT 1 FROM aclexplode(d.defaclacl) a WHERE a.grantee=owner_oid))
  OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='public' AND has_schema_privilege(owner_oid,oid,'CREATE'))
  OR EXISTS(SELECT 1 FROM pg_database WHERE datname=current_database() AND has_database_privilege(owner_oid,oid,'CREATE'))
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 SELECT array_agg(to_regclass('public.'||t)::oid) INTO fact_oids FROM unnest(tables) t;
 IF array_position(fact_oids,NULL) IS NOT NULL OR (SELECT count(DISTINCT x) FROM unnest(fact_oids) x)<>15
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a
   WHERE c.relnamespace='public'::regnamespace AND a.grantee=owner_oid
    AND (NOT(c.oid=ANY(fact_oids)) OR a.privilege_type<>'SELECT' OR a.is_grantable))
  OR (SELECT count(DISTINCT c.oid) FROM pg_class c,LATERAL aclexplode(c.relacl) a
   WHERE c.relnamespace='public'::regnamespace AND a.grantee=owner_oid)<>15
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM pg_class c JOIN pg_attribute x ON x.attrelid=c.oid,LATERAL aclexplode(x.attacl) a
   WHERE a.grantee=owner_oid AND (a.privilege_type<>'UPDATE' OR a.is_grantable OR NOT EXISTS(
    SELECT 1 FROM jsonb_each_text(locks) l WHERE c.oid=to_regclass('public.'||l.key) AND x.attname=l.value)))
  OR (SELECT count(DISTINCT (c.oid,x.attname)) FROM pg_class c JOIN pg_attribute x ON x.attrelid=c.oid,
    LATERAL aclexplode(x.attacl) a WHERE a.grantee=owner_oid)<>5
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM pg_class c WHERE c.relnamespace='public'::regnamespace AND c.relkind IN('r','v','m','p','f')
   AND (has_table_privilege(owner_oid,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
    OR (NOT(c.oid=ANY(fact_oids)) AND (has_table_privilege(owner_oid,c.oid,'SELECT')
     OR has_any_column_privilege(owner_oid,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')))))
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
   WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped
    AND EXISTS(SELECT 1 FROM aclexplode(a.attacl) acl WHERE acl.grantee IN (owner_oid,0::oid) AND acl.privilege_type IN ('INSERT','REFERENCES','UPDATE'))
    AND NOT EXISTS(SELECT 1 FROM jsonb_each_text(locks) l WHERE c.oid=to_regclass('public.'||l.key) AND a.attname=l.value))
  OR (SELECT count(DISTINCT (c.oid,a.attname)) FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
   WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped
    AND EXISTS(SELECT 1 FROM aclexplode(a.attacl) acl WHERE acl.grantee IN (owner_oid,0::oid) AND acl.privilege_type IN ('INSERT','REFERENCES','UPDATE')))<>5
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 FOREACH tab IN ARRAY tables LOOP
  IF tab IN ('meta_object_type','meta_action_type') THEN CONTINUE; END IF;
  expression:=tenant;
  IF tab='aip_action_proposal' THEN
   expression:='('||substring(tenant FROM 2 FOR length(tenant)-2)||' AND (action_type_id = ANY (ARRAY[''aip_request_provider_capacity''::text, ''aip_review_provider_capacity_source''::text])) AND ((action_type_snapshot ->> ''id''::text) = action_type_id))';
  ELSIF tab IN ('aip_action_draft','aip_action_approval_event') THEN
   expression:='('||substring(tenant FROM 2 FOR length(tenant)-2)||' AND (EXISTS ( SELECT 1 FROM public.aip_action_proposal p WHERE ((p.org_id = '||tab||'.org_id) AND (p.project_id = '||tab||'.project_id) AND (p.proposal_id = '||tab||'.proposal_id)))))';
  END IF;
  SELECT * INTO flags FROM pg_class WHERE oid=to_regclass('public.'||tab);
  IF NOT flags.relrowsecurity OR NOT flags.relforcerowsecurity
  THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
  SELECT count(*) INTO n FROM pg_policy WHERE polrelid=flags.oid AND owner_oid=ANY(polroles);
  IF n<>2 OR EXISTS(SELECT 1 FROM pg_policy p WHERE p.polrelid=flags.oid AND owner_oid=ANY(p.polroles)
    AND (p.polname NOT IN ('capacity_publication_fact_a0v155','capacity_publication_fact_restrict_a0v155')
     OR p.polcmd<>'*' OR p.polpermissive<>(p.polname='capacity_publication_fact_a0v155')
     OR p.polroles<>ARRAY[owner_oid] OR
     regexp_replace(trim(coalesce(pg_get_expr(p.polqual,p.polrelid),'')),E'\\s+',' ','g')<>
      regexp_replace(trim(expression),E'\\s+',' ','g') OR
     regexp_replace(trim(coalesce(pg_get_expr(p.polwithcheck,p.polrelid),'')),E'\\s+',' ','g')<>
      regexp_replace(trim(expression),E'\\s+',' ','g')))
  THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 END LOOP;
 SELECT * INTO g FROM pg_proc WHERE oid=to_regprocedure('public.capacity_publication_owner_read_lock_only_a0v155()');
 IF NOT FOUND OR g.proowner<>owner_oid OR g.prosecdef OR g.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']
  OR g.prorettype<>2279 OR g.proargtypes::text<>''
  OR encode(sha256(convert_to(g.prosrc,'UTF8')),'hex')<>'3270bc4120dd7bfeadd75b7506914ec1653df938a5adc7f71cec41fffd9893c1'
  OR EXISTS(SELECT 1 FROM aclexplode(g.proacl) a WHERE a.grantee<>g.proowner)
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
 IF (SELECT count(*) FROM pg_trigger WHERE tgname='capacity_publication_owner_read_lock_only_a0v155')<>5
  OR EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgname='capacity_publication_owner_read_lock_only_a0v155'
    AND (NOT EXISTS(SELECT 1 FROM jsonb_each_text(locks) l WHERE t.tgrelid=to_regclass('public.'||l.key))
     OR t.tgfoid<>g.oid OR t.tgenabled<>'O' OR t.tgtype<>31 OR t.tgqual IS NOT NULL
     OR t.tgargs<>''::bytea OR t.tgnargs<>0 OR cardinality(t.tgattr::smallint[])<>0))
 THEN RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED' USING ERRCODE='22023'; END IF;
END 