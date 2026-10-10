"""Read-only catalogue coverage supplementary to snapshot_all; no effects."""
import copy,json,re
from snapshot_all import rows,require_schema_set
FIELDS=frozenset(('database','database_acl','database_role_settings','sequence_definitions','type_acl','domain_constraints','collations','comments','dependencies','shared_dependencies','inheritance','extension_config','tablespaces'))
def require_routine_kinds(kinds):
 if any(k not in ('f','p') for k in kinds):raise ValueError('UNREVIEWED_ROUTINE_KIND')

OBJECT_NAME=re.compile(r'(?<![A-Za-z0-9_])RI_ConstraintTrigger_[ac]_[0-9]+(?![A-Za-z0-9_])')

def canonical(value,triggers):
 result=copy.deepcopy(value)
 mapping={r['tgname']:r['tgname'].rsplit('_',1)[0]+'_GENERATED_OID' for r in triggers if r['tgisinternal'] and re.fullmatch(r'RI_ConstraintTrigger_[ac]_[0-9]+',r['tgname'])}
 for field in ('comments','dependencies','shared_dependencies'):
  for r in result[field]:
   for prefix in ('object','referenced'):
    if r.get(prefix+'_type')=='trigger':
     for key in (prefix+'_identity',prefix+'_name'):
      if isinstance(r.get(key),str):
       r[key]=OBJECT_NAME.sub(lambda match:mapping.get(match[0],match[0]),r[key])
  result[field].sort(key=lambda r:json.dumps(r,sort_keys=True))
 return result

def require_supplement_equivalent(before,after):
 if set(before)!=FIELDS or set(after)!=FIELDS:raise ValueError('SUPPLEMENT_COVERAGE_REQUIRED')
 if before!=after:raise ValueError('SUPPLEMENT_RESTORE_DIFFERENCE')
 return True

# Identify-object resolves qualified names; dependency OIDs never enter proof.
USER_OBJECTS="""SELECT 'pg_class'::regclass AS classid,c.oid AS objid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_proc'::regclass,p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_type'::regclass,t.oid FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_namespace'::regclass,n.oid FROM pg_namespace n WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_attrdef'::regclass,d.oid FROM pg_attrdef d JOIN pg_class c ON c.oid=d.adrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_constraint'::regclass,k.oid FROM pg_constraint k JOIN pg_namespace n ON n.oid=k.connamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_trigger'::regclass,t.oid FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_policy'::regclass,p.oid FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_collation'::regclass,c.oid FROM pg_collation c JOIN pg_namespace n ON n.oid=c.collnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')
 UNION SELECT 'pg_extension'::regclass,e.oid FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')"""
SPECS={
 'database':"SELECT datname,pg_get_userbyid(datdba) AS owner,pg_encoding_to_char(encoding) AS encoding,datlocprovider,datcollate,datctype,daticulocale,datcollversion,datconnlimit,datallowconn,datistemplate,(SELECT spcname FROM pg_tablespace WHERE oid=dattablespace) AS tablespace FROM pg_database WHERE datname=current_database()",
 'database_acl':"SELECT pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable FROM pg_database d CROSS JOIN LATERAL aclexplode(coalesce(d.datacl,acldefault('d',d.datdba))) x WHERE d.datname=current_database()",
 'database_role_settings':"SELECT CASE WHEN setrole=0 THEN 'ALL' ELSE pg_get_userbyid(setrole) END AS role,setconfig FROM pg_db_role_setting WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname=current_database())",
 'sequence_definitions':"SELECT n.nspname,c.relname,format_type(s.seqtypid,-1) AS type,s.seqstart,s.seqincrement,s.seqmax,s.seqmin,s.seqcache,s.seqcycle FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')",
 'type_acl':"SELECT n.nspname,t.typname,pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace CROSS JOIN LATERAL aclexplode(coalesce(t.typacl,acldefault('T',t.typowner))) x WHERE n.nspname IN ('public','aos_capacity_publication_private')",
 'domain_constraints':"SELECT n.nspname,t.typname,k.conname,k.convalidated,k.condeferrable,k.condeferred,pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k JOIN pg_type t ON t.oid=k.contypid JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')",
 'collations':"SELECT n.nspname,c.collname,pg_get_userbyid(c.collowner) AS owner,c.collprovider,c.collisdeterministic,c.collencoding,c.collcollate,c.collctype,c.colliculocale,c.collversion FROM pg_collation c JOIN pg_namespace n ON n.oid=c.collnamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')",
 'inheritance':"SELECT a.nspname AS child_schema,c.relname AS child,b.nspname AS parent_schema,p.relname AS parent,i.inhseqno,i.inhdetachpending FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid JOIN pg_namespace a ON a.oid=c.relnamespace JOIN pg_class p ON p.oid=i.inhparent JOIN pg_namespace b ON b.oid=p.relnamespace WHERE a.nspname IN ('public','aos_capacity_publication_private') OR b.nspname IN ('public','aos_capacity_publication_private')",
 'extension_config':"SELECT extname,ARRAY(SELECT x::regclass::text FROM unnest(extconfig) x ORDER BY x::regclass::text) AS relations,extcondition FROM pg_extension",
 'tablespaces':"SELECT spcname,pg_get_userbyid(spcowner) AS owner,spcoptions,pg_tablespace_location(oid) AS location FROM pg_tablespace",
}
def supplement(conn,version='a0v_157'):
 if not conn.read_only:raise ValueError('READ_ONLY_TRANSACTION_REQUIRED')
 schemas=[r[0] for r in conn.execute("SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname<>'information_schema' ORDER BY 1")];require_schema_set(schemas,version=version)
 if conn.execute('SELECT version_num FROM public.alembic_version').fetchall()!=[(version,)]:raise ValueError('EXACT_DATABASE_VERSION_REQUIRED')
 clause="IN ("+','.join("'"+x+"'" for x in sorted(schemas))+")"
 original="IN ('public','aos_capacity_publication_private')"
 scoped=lambda text:text.replace(original,clause)
 objects=scoped(USER_OBJECTS)
 kinds=[r[0] for r in conn.execute(scoped("SELECT DISTINCT prokind FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('public','aos_capacity_publication_private')"))];require_routine_kinds(kinds)
 result={k:rows(conn,scoped(q)) for k,q in SPECS.items()}
 result['comments']=rows(conn,"WITH u AS ("+objects+") SELECT o.type AS object_type,o.schema AS object_schema,o.name AS object_name,o.identity AS object_identity,d.description FROM pg_description d CROSS JOIN LATERAL pg_identify_object(d.classoid,d.objoid,d.objsubid) o WHERE EXISTS(SELECT 1 FROM u WHERE u.classid=d.classoid AND u.objid=d.objoid)")
 result['dependencies']=rows(conn,"WITH u AS ("+objects+") SELECT o.type AS object_type,o.schema AS object_schema,o.name AS object_name,o.identity AS object_identity,r.type AS referenced_type,r.schema AS referenced_schema,r.name AS referenced_name,r.identity AS referenced_identity,d.deptype FROM pg_depend d CROSS JOIN LATERAL pg_identify_object(d.classid,d.objid,d.objsubid) o CROSS JOIN LATERAL pg_identify_object(d.refclassid,d.refobjid,d.refobjsubid) r WHERE EXISTS(SELECT 1 FROM u WHERE (u.classid=d.classid AND u.objid=d.objid) OR (u.classid=d.refclassid AND u.objid=d.refobjid))")
 result['shared_dependencies']=rows(conn,"SELECT o.type AS object_type,o.schema AS object_schema,o.name AS object_name,o.identity AS object_identity,r.type AS referenced_type,r.schema AS referenced_schema,r.name AS referenced_name,r.identity AS referenced_identity,d.deptype FROM pg_shdepend d CROSS JOIN LATERAL pg_identify_object(d.classid,d.objid,d.objsubid) o CROSS JOIN LATERAL pg_identify_object(d.refclassid,d.refobjid,0) r WHERE d.dbid=(SELECT oid FROM pg_database WHERE datname=current_database())")
 assert set(result)==FIELDS
 return result
