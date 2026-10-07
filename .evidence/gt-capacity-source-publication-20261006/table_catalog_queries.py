"""Trusted fixed catalog queries for the five future Source tables; no DDL."""
TABLE_NAMES = ('global_account','global_provider','source_pending','source_publication','source_provenance')
QUERIES = {
 'columns': """SELECT a.attnum,a.attname,tn.nspname AS type_schema,t.typname AS type_name,
    a.atttypmod,a.attnotnull,a.attidentity,a.attgenerated,a.attisdropped,
    CASE WHEN a.attcollation=0 THEN NULL ELSE cn.nspname||'.'||cl.collname END AS collation,
    pg_get_expr(d.adbin,d.adrelid) AS default_expr FROM pg_attribute a
    JOIN pg_type t ON t.oid=a.atttypid JOIN pg_namespace tn ON tn.oid=t.typnamespace
    LEFT JOIN pg_collation cl ON cl.oid=a.attcollation LEFT JOIN pg_namespace cn ON cn.oid=cl.collnamespace
    LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
    WHERE a.attrelid=%s AND a.attnum>0 ORDER BY a.attnum""",
 'acl': """SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee)::text END AS grantee,
    pg_get_userbyid(a.grantor)::text AS grantor,a.privilege_type,a.is_grantable
    FROM pg_class p,LATERAL aclexplode(coalesce(p.relacl,acldefault('r',p.relowner))) a
    WHERE p.oid=%s ORDER BY grantee,grantor,privilege_type,is_grantable""",
 'column_acl': """SELECT a.attname,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee)::text END AS grantee,
    pg_get_userbyid(x.grantor)::text AS grantor,x.privilege_type,x.is_grantable
    FROM pg_attribute a,LATERAL aclexplode(a.attacl) x WHERE a.attrelid=%s
    ORDER BY attname,grantee,grantor,privilege_type,is_grantable""",
 'policies': """SELECT polname,polcmd,polpermissive,
    ARRAY(SELECT CASE WHEN r=0 THEN 'PUBLIC' ELSE pg_get_userbyid(r)::text END FROM unnest(polroles) r ORDER BY 1) AS roles,
    pg_get_expr(polqual,polrelid) AS using_expr,pg_get_expr(polwithcheck,polrelid) AS check_expr
    FROM pg_policy WHERE polrelid=%s ORDER BY polname""",
 'constraints': """SELECT conname,contype,condeferrable,condeferred,convalidated,conislocal,coninhcount,connoinherit,
    pg_get_constraintdef(oid,false) AS definition FROM pg_constraint WHERE conrelid=%s ORDER BY conname""",
 'indexes': """SELECT x.relname AS name,n.nspname AS schema,am.amname AS method,
    i.indisunique,i.indisprimary,i.indisvalid,i.indisready,i.indislive,i.indisexclusion,i.indimmediate,
    i.indnullsnotdistinct,i.indisreplident,i.indnkeyatts,i.indnatts,i.indkey::smallint[] AS keys,
    i.indoption::smallint[] AS options,
    ARRAY(SELECT ns.nspname||'.'||op.opcname FROM unnest(i.indclass::oid[]) WITH ORDINALITY z(id,pos)
          JOIN pg_opclass op ON op.oid=z.id JOIN pg_namespace ns ON ns.oid=op.opcnamespace ORDER BY z.pos) AS opclasses,
    ARRAY(SELECT CASE WHEN z.id=0 THEN NULL ELSE ns.nspname||'.'||cl.collname END
          FROM unnest(i.indcollation::oid[]) WITH ORDINALITY z(id,pos)
          LEFT JOIN pg_collation cl ON cl.oid=z.id LEFT JOIN pg_namespace ns ON ns.oid=cl.collnamespace ORDER BY z.pos) AS collations,
    pg_get_expr(i.indexprs,i.indrelid) AS expressions,pg_get_expr(i.indpred,i.indrelid) AS predicate,
    x.reloptions,pg_get_indexdef(i.indexrelid) AS definition
    FROM pg_index i JOIN pg_class x ON x.oid=i.indexrelid JOIN pg_namespace n ON n.oid=x.relnamespace
    JOIN pg_am am ON am.oid=x.relam WHERE i.indrelid=%s ORDER BY name""",
 'triggers': """SELECT CASE WHEN t.tgisinternal THEN NULL ELSE t.tgname END AS name,
    t.tgenabled,t.tgtype,t.tgdeferrable,t.tginitdeferred,t.tgisinternal,
    ns.nspname||'.'||quote_ident(p.proname)||'('||pg_get_function_identity_arguments(p.oid)||')' AS function,
    co.conname AS constraint_name,co.contype AS constraint_type,
    co.conrelid::regclass::text AS constraint_table,co.confrelid::regclass::text AS referenced_table,
    CASE WHEN t.tgconstrrelid=0 THEN NULL ELSE t.tgconstrrelid::regclass::text END AS related_table,
    t.tgnargs,encode(t.tgargs,'hex') AS arguments,t.tgattr::smallint[] AS columns,
    pg_get_expr(t.tgqual,t.tgrelid) AS condition
    FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace ns ON ns.oid=p.pronamespace
    LEFT JOIN pg_constraint co ON co.oid=t.tgconstraint WHERE t.tgrelid=%s
    ORDER BY name NULLS LAST,constraint_name,function,tgtype""",
}
PROPERTIES = """SELECT c.relname,c.relkind,c.relpersistence,c.relrowsecurity,c.relforcerowsecurity,
    c.relreplident,c.relispartition,c.relhassubclass,c.relhasrules,c.reloptions,
    r.rolname AS owner,n.nspname AS schema,
    EXISTS(SELECT 1 FROM pg_inherits WHERE inhrelid=c.oid OR inhparent=c.oid) AS inheritance
    FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.oid=%s"""

def catalog(conn):
    result={}
    for name in TABLE_NAMES:
        oid=conn.execute('SELECT to_regclass(%s)::oid AS oid',('aos_capacity_publication_private.'+name,)).fetchone()['oid']
        if oid is None:
            result[name]=None
            continue
        table=conn.execute(PROPERTIES,(oid,)).fetchone()
        for key,query in QUERIES.items():table[key]=conn.execute(query,(oid,)).fetchall()
        result[name]=table
    return result
