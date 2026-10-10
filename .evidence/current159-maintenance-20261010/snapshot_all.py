"""Read-only all-schema snapshot for fixed current157 maintenance.

Contains no connection, migration, service control or restore operation.
Catalog uses qualified names and resolved role names rather than restore OIDs.
Data snapshots contain hashes only. Comparison is strict; differences need review.
"""
import hashlib
import json
from psycopg import sql
SCHEMAS=frozenset(('public','aos_capacity_publication_private'))

def qualified(schema,name):
    return sql.Identifier(schema,name)

def require_schema_set(schemas):
    if set(schemas)!=SCHEMAS or len(schemas)!=len(SCHEMAS):
        raise ValueError('ALL_SCHEMA_SCOPE_DRIFT')

def compare_exact(before,after):
    if before!=after:
        raise ValueError('ALL_SCHEMA_RESTORE_DIFFERENCE')
    return True

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

CATALOG={
 'schemas':"SELECT nspname,pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname=ANY(%s)",
 'relations':"SELECT n.nspname,c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity,c.relreplident,c.relpersistence,c.reloptions,pg_get_userbyid(c.relowner) AS owner,am.amname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_am am ON am.oid=c.relam WHERE n.nspname=ANY(%s)",
 'columns':"SELECT n.nspname,c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull,a.attidentity,a.attgenerated,a.attstorage,a.attcompression,a.attstattarget,a.attoptions,pg_get_expr(d.adbin,d.adrelid) AS default FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped",
 'constraints':"SELECT n.nspname,c.relname,k.conname,k.contype,k.convalidated,k.condeferrable,k.condeferred,pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s)",
 'indexes':"SELECT n.nspname,c.relname,i.relname AS index,x.indisvalid,x.indisready,x.indislive,pg_get_indexdef(i.oid) AS definition FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s)",
 'triggers':"SELECT n.nspname,c.relname,t.tgname,t.tgenabled,t.tgisinternal,pg_get_triggerdef(t.oid) AS definition FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s)",
 'functions':"SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) AS args,pg_get_userbyid(p.proowner) AS owner,pg_get_functiondef(p.oid) AS definition FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=ANY(%s) AND p.prokind IN ('f','p')",
 'policies':"SELECT n.nspname,c.relname,p.polname,p.polpermissive,p.polcmd,ARRAY(SELECT CASE WHEN r=0 THEN 'PUBLIC' ELSE pg_get_userbyid(r) END FROM unnest(p.polroles) r ORDER BY 1) AS roles,pg_get_expr(p.polqual,p.polrelid) AS qual,pg_get_expr(p.polwithcheck,p.polrelid) AS check FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s)",
 'column_acl':"SELECT n.nspname,c.relname,a.attname,pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname=ANY(%s)",
 'relation_acl':"SELECT n.nspname,c.relname,pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault((CASE WHEN c.relkind='S' THEN 'S' ELSE 'r' END)::\"char\",c.relowner))) x WHERE n.nspname=ANY(%s)",
 'schema_acl':"SELECT n.nspname,pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable FROM pg_namespace n CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) x WHERE n.nspname=ANY(%s)",
 'function_acl':"SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) AS args,pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) x WHERE n.nspname=ANY(%s)",
 'default_acl':"SELECT pg_get_userbyid(a.defaclrole) AS owner,coalesce(n.nspname,'GLOBAL') AS schema,a.defaclobjtype,pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable FROM pg_default_acl a LEFT JOIN pg_namespace n ON n.oid=a.defaclnamespace CROSS JOIN LATERAL aclexplode(a.defaclacl) x WHERE n.nspname=ANY(%s) OR a.defaclnamespace=0",
 'types':"SELECT n.nspname,t.typname,t.typtype,pg_get_userbyid(t.typowner) AS owner,format_type(t.typbasetype,t.typtypmod) AS base,t.typnotnull,t.typdefault,ARRAY(SELECT e.enumlabel FROM pg_enum e WHERE e.enumtypid=t.oid ORDER BY e.enumsortorder) AS labels FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname=ANY(%s)",
 'extensions':"SELECT e.extname,e.extversion,pg_get_userbyid(e.extowner) AS owner,n.nspname,e.extrelocatable FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE n.nspname=ANY(%s)",
}

def rows(conn,statement,params=None):
    return conn.execute('SELECT coalesce(json_agg(r ORDER BY row_to_json(r)::text),\'[]\'::json) FROM ('+statement+') r',params).fetchone()[0]

def snapshot(conn):
    if not conn.read_only:
        raise ValueError('READ_ONLY_TRANSACTION_REQUIRED')
    conn.execute("SET LOCAL timezone='UTC'")
    conn.execute('SET LOCAL search_path=pg_catalog,public')
    schemas=[r[0] for r in conn.execute("SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname<>'information_schema' ORDER BY 1")]
    require_schema_set(schemas)
    relations=conn.execute('SELECT n.nspname,c.relname,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2',(schemas,)).fetchall()
    if any(r[2] not in ('r','i','S') for r in relations):
        raise ValueError('UNREVIEWED_RELATION_KIND')
    result={k:rows(conn,q,(schemas,)) for k,q in CATALOG.items()}
    result['roles']=rows(conn,"SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolconnlimit,rolvaliduntil,rolbypassrls,rolconfig FROM pg_roles")
    result['role_memberships']=rows(conn,"SELECT pg_get_userbyid(roleid) AS role,pg_get_userbyid(member) AS member,pg_get_userbyid(grantor) AS grantor,admin_option,inherit_option,set_option FROM pg_auth_members")
    result['event_triggers']=rows(conn,"SELECT evtname,evtevent,pg_get_userbyid(evtowner) AS owner,evtfoid::regprocedure::text AS function,evtenabled,evttags FROM pg_event_trigger")
    result['sequences']={};result['tables']={}
    for schema,name,kind in relations:
        key=json.dumps([schema,name],separators=(',',':'))
        if kind=='r':
            r=conn.execute(sql.SQL("SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') FROM (SELECT encode(sha256(convert_to(row_to_json(t)::text,'UTF8')),'hex') AS h FROM {} t) x").format(qualified(schema,name))).fetchone()
            result['tables'][key]={'rows':r[0],'sha256':r[1]}
        elif kind=='S':
            r=conn.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(qualified(schema,name))).fetchone()
            result['sequences'][key]={'last_value':r[0],'is_called':r[1]}
    result['version']=conn.execute('SELECT version_num FROM public.alembic_version').fetchall()[0][0]
    return result
