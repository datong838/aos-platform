"""Deterministic catalog snapshot shared by private authority admissions."""


class AuthoritySchemaBlocked(RuntimeError):
    pass


def authority_schema_snapshot(conn, *, tables, function_owners):
    """Catalog-only structural evidence. No business rows or credentials read."""
    table_names = tables
    tables = {}
    for name in table_names:
        table = conn.execute("""SELECT c.oid,c.relkind,c.relrowsecurity,c.relforcerowsecurity,
            c.relowner::regrole::text AS owner FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname=%s""", (name,)).fetchone()
        if table is None or table['owner'] != 'aos_app':
            raise AuthoritySchemaBlocked('BUDGET_COST_SCHEMA_OWNER_REQUIRED')
        oid = table.pop('oid')
        table.pop('owner')
        table['columns'] = conn.execute("""SELECT a.attname AS name,
            format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull AS required,
            pg_get_expr(d.adbin,d.adrelid) AS default,a.attidentity AS identity,a.attgenerated AS generated,
            (SELECT coalesce(jsonb_agg(jsonb_build_array(CASE WHEN x.grantee=c.relowner THEN '<owner>'
                WHEN x.grantee=0 THEN 'PUBLIC' ELSE x.grantee::regrole::text END,
                x.privilege_type,x.is_grantable) ORDER BY x.grantee::regrole::text,x.privilege_type),'[]'::jsonb)
             FROM aclexplode(a.attacl) x) AS acl
            FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
            LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""", (oid,)).fetchall()
        table['constraints'] = conn.execute("""SELECT conname AS name,contype AS type,
            pg_get_constraintdef(oid) AS definition,convalidated AS validated
            FROM pg_catalog.pg_constraint WHERE conrelid=%s ORDER BY conname""", (oid,)).fetchall()
        table['indexes'] = conn.execute("""SELECT pg_get_indexdef(indexrelid) AS definition,
            indisvalid AS valid,indisready AS ready FROM pg_catalog.pg_index
            WHERE indrelid=%s ORDER BY indexrelid::regclass::text""", (oid,)).fetchall()
        table['policies'] = conn.execute("""SELECT polname AS name,polpermissive AS permissive,
            polcmd AS command,ARRAY(SELECT r::regrole::text FROM unnest(polroles) r ORDER BY r::regrole::text) AS roles,
            pg_get_expr(polqual,polrelid) AS using,pg_get_expr(polwithcheck,polrelid) AS check
            FROM pg_catalog.pg_policy WHERE polrelid=%s ORDER BY polname""", (oid,)).fetchall()
        table['triggers'] = conn.execute("""SELECT tgname AS name,tgenabled AS enabled,
            pg_get_triggerdef(oid) AS definition FROM pg_catalog.pg_trigger
            WHERE tgrelid=%s AND NOT tgisinternal ORDER BY tgname""", (oid,)).fetchall()
        table['acl'] = conn.execute("""SELECT CASE WHEN x.grantee=c.relowner THEN '<owner>'
            WHEN x.grantee=0 THEN 'PUBLIC' ELSE x.grantee::regrole::text END AS grantee,
            x.privilege_type AS privilege,x.is_grantable AS grantable
            FROM pg_catalog.pg_class c,LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) x
            WHERE c.oid=%s ORDER BY grantee,privilege""", (oid,)).fetchall()
        tables[name] = table
    functions = {}
    for name, owner in function_owners.items():
        row = conn.execute("""SELECT p.proowner::regrole::text AS owner,
            pg_get_functiondef(p.oid) AS definition,
            (SELECT jsonb_agg(jsonb_build_array(CASE WHEN x.grantee=p.proowner THEN '<owner>'
                WHEN x.grantee=0 THEN 'PUBLIC' ELSE x.grantee::regrole::text END,
                x.privilege_type,x.is_grantable) ORDER BY
                CASE WHEN x.grantee=p.proowner THEN '<owner>' WHEN x.grantee=0 THEN 'PUBLIC'
                ELSE x.grantee::regrole::text END,x.privilege_type)
             FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) x) AS acl
            FROM pg_catalog.pg_proc p WHERE p.oid=to_regprocedure(%s)""", (name,)).fetchone()
        if row is None or row.pop('owner') != owner:
            raise AuthoritySchemaBlocked('BUDGET_COST_SCHEMA_OWNER_REQUIRED')
        functions[name] = row
    return dict(tables=tables, functions=functions)
