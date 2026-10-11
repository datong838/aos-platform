"""Explicit catalog audit family; no automatic installation or execution grant.

Role/table guards in the original audit exclude inherited and table privileges
before inspecting column ACLs. Equivalent explicit ACL predicates and NULL
prefilters retain every grant check; trusted original SQL and every legacy
compiler remain unchanged.
"""
import hashlib
import re

from aos_api import aip_provider_capacity_occupation_epoch_profile as epoch
from aos_api import aip_provider_capacity_publication_store as store

FACT = 'aos_capacity_publication_private.require_original_fact_boundary()'
COLUMN_BEFORE = ("(has_column_privilege(owner_oid,c.oid,a.attnum,'INSERT,REFERENCES')\n"
                 "      OR has_column_privilege(owner_oid,c.oid,a.attnum,'UPDATE'))")
COLUMN_AFTER = ("(a.attacl IS NOT NULL AND EXISTS(SELECT 1 FROM aclexplode(a.attacl) acl "
                "WHERE acl.grantee IN (owner_oid,0::oid) "
                "AND acl.privilege_type IN ('INSERT','REFERENCES','UPDATE')))")
# NULL ACLs produce no aclexplode rows. Expose this filter before the catalog
# joins while retaining scans across every schema and every original grant.
GLOBAL_COLUMN_FILTERS = tuple(
    ('LATERAL aclexplode(x.attacl) a' + gap + 'WHERE a.grantee=owner_oid',
     'LATERAL aclexplode(x.attacl) a' + gap + 'WHERE x.attacl IS NOT NULL AND a.grantee=owner_oid')
    for gap in ('\n   ', ' ')
)
# Audit the same complete Owner ACL set once. DISTINCT still counts columns,
# while bool_or catches every forbidden privilege, grant option and location.
GLOBAL_AGGREGATE_BEFORE = """EXISTS(SELECT 1 FROM pg_class c JOIN pg_attribute x ON x.attrelid=c.oid,LATERAL aclexplode(x.attacl) a
   WHERE x.attacl IS NOT NULL AND a.grantee=owner_oid AND (a.privilege_type<>'UPDATE' OR a.is_grantable OR NOT EXISTS(
    SELECT 1 FROM jsonb_each_text(locks) l WHERE c.oid=to_regclass('public.'||l.key) AND x.attname=l.value)))
  OR (SELECT count(DISTINCT (c.oid,x.attname)) FROM pg_class c JOIN pg_attribute x ON x.attrelid=c.oid,
    LATERAL aclexplode(x.attacl) a WHERE x.attacl IS NOT NULL AND a.grantee=owner_oid)<>5"""
GLOBAL_AGGREGATE_AFTER = """(SELECT coalesce(bool_or(a.privilege_type<>'UPDATE' OR a.is_grantable OR NOT EXISTS(SELECT 1 FROM jsonb_each_text(locks) l WHERE c.oid=to_regclass('public.'||l.key) AND x.attname=l.value)),false) OR count(DISTINCT (c.oid,x.attname))<>5 FROM pg_class c JOIN pg_attribute x ON x.attrelid=c.oid,LATERAL aclexplode(x.attacl) a WHERE x.attacl IS NOT NULL AND a.grantee=owner_oid)"""
# Keep the public writable-column set and its exact distinct cardinality.
PUBLIC_AGGREGATE_BEFORE = """EXISTS(SELECT 1 FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
   WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped
    AND (a.attacl IS NOT NULL AND EXISTS(SELECT 1 FROM aclexplode(a.attacl) acl WHERE acl.grantee IN (owner_oid,0::oid) AND acl.privilege_type IN ('INSERT','REFERENCES','UPDATE')))
    AND NOT EXISTS(SELECT 1 FROM jsonb_each_text(locks) l WHERE c.oid=to_regclass('public.'||l.key) AND a.attname=l.value))
  OR (SELECT count(DISTINCT (c.oid,a.attname)) FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
   WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped
    AND (a.attacl IS NOT NULL AND EXISTS(SELECT 1 FROM aclexplode(a.attacl) acl WHERE acl.grantee IN (owner_oid,0::oid) AND acl.privilege_type IN ('INSERT','REFERENCES','UPDATE'))))<>5"""
PUBLIC_AGGREGATE_AFTER = """(SELECT coalesce(bool_or(NOT EXISTS(SELECT 1 FROM jsonb_each_text(locks) l WHERE c.oid=to_regclass('public.'||l.key) AND a.attname=l.value)),false) OR count(DISTINCT (c.oid,a.attname))<>5 FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped AND (a.attacl IS NOT NULL AND EXISTS(SELECT 1 FROM aclexplode(a.attacl) acl WHERE acl.grantee IN (owner_oid,0::oid) AND acl.privilege_type IN ('INSERT','REFERENCES','UPDATE'))))"""
ERROR = 'CAPACITY_CATALOG_PROFILE_INSTALLATION_DRIFTED'


def _profile_body(ddl):
    matches = re.findall(r'AS \$profile\$(.*?)\$profile\$;', ddl, re.S)
    if len(matches) != 1:
        raise ValueError(ERROR)
    return matches[0]


def _digest(body):
    return hashlib.sha256(body.encode()).hexdigest()


def catalog_fact_body():
    original = epoch._body(store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL, FACT)
    body = epoch._replace(original, COLUMN_BEFORE, COLUMN_AFTER, 2)
    for before, after in GLOBAL_COLUMN_FILTERS:
        body = epoch._replace(body, before, after)
    body = epoch._replace(body, GLOBAL_AGGREGATE_BEFORE, GLOBAL_AGGREGATE_AFTER)
    return epoch._replace(body, PUBLIC_AGGREGATE_BEFORE, PUBLIC_AGGREGATE_AFTER)


def catalog_private_statements():
    """Compile FACT plus complete original three-lock private identity."""
    previous = epoch.occupation_epoch_profile_statements()
    original = epoch._body(store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL, FACT)
    fact = catalog_fact_body()
    audit = epoch._replace(_profile_body(previous[-1]), _digest(original), _digest(fact))
    return (epoch._definition(FACT, fact), *previous[:-1],
            epoch._definition(epoch.INSTALLATION, audit))


def _audit_hashes():
    return (_digest(_profile_body(epoch.occupation_epoch_profile_statements()[-1])),
            _digest(_profile_body(catalog_private_statements()[-1])))


def catalog_public_statements(*, include_consumer=False):
    before, after = _audit_hashes()
    statements = []
    for statement in epoch.occupation_public_source_profile_statements(include_consumer=include_consumer)[4:]:
        if statement.startswith('CREATE OR REPLACE FUNCTION public.'):
            statement = epoch._replace(statement, before, after)
        statements.append(statement)
    return (*catalog_private_statements(), *statements)


def catalog_public_manifest(*, include_consumer=False):
    from aos_api import aip_provider_capacity_publication_transaction as transaction
    return transaction._trusted_function_manifest(tuple(
        s.replace('CREATE OR REPLACE FUNCTION public.', 'CREATE FUNCTION public.')
        for s in catalog_public_statements(include_consumer=include_consumer)[5:]))


def catalog_occupation_statements():
    from aos_api import aip_provider_capacity_occupation_source as occupation
    before, after = _audit_hashes()
    statements = list(occupation.occupation_source_statements())
    statements[4] = epoch._replace(statements[4], before, after)
    return tuple(statements)


def catalog_installation_statements(*, include_consumer=False):
    """Complete explicit installer artifact; run only in an owned install gate."""
    occupation = tuple(s.replace('CREATE FUNCTION public.', 'CREATE OR REPLACE FUNCTION public.')
                       for s in catalog_occupation_statements())
    return (*catalog_public_statements(include_consumer=include_consumer), *occupation)


def catalog_profile_is_installed(conn):
    """Recognize private identity exactly; public/occupation callers audit theirs.

    Partial new identities fail closed, including a removed lock grant. Trust
    comes from the fixed compiler, never from caller SQL or target-body hashes.
    """
    statements = catalog_private_statements()
    definitions = ((FACT, statements[0]), (epoch.PAIR, statements[2]),
                   (epoch.EVIDENCE, statements[3]), (epoch.INSTALLATION, statements[4]))
    rows = {}
    for signature, ddl in definitions:
        row = conn.execute("""SELECT p.oid,p.prosrc,r.rolname,p.prosecdef,p.proisstrict,p.proconfig,
            p.provolatile,p.proparallel,p.prokind,p.proretset,p.prorettype,p.pronargs,p.pronargdefaults,
            p.provariadic,p.proleakproof,p.prosupport::oid AS prosupport,l.lanname,p.proargtypes::text AS args
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_roles r ON r.oid=p.proowner JOIN pg_language l ON l.oid=p.prolang
            WHERE n.nspname=%s AND p.proname=%s AND p.pronargs=0""",
            (signature.split('.')[0], signature.split('.')[1].split('(')[0])).fetchone()
        rows[signature] = (row, _profile_body(ddl))
    # Only new FACT/private-audit bodies identify this family. Shared PAIR and
    # EVIDENCE alone remain valid identifiers for the original epoch profile.
    if not any(rows[s][0] and rows[s][0]['prosrc'] == rows[s][1]
               for s in (FACT, epoch.INSTALLATION)):
        return False
    extra = conn.execute("""SELECT EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a
        WHERE p.oid=to_regprocedure(%s) AND a.grantee=to_regrole('aos_capacity_publication_owner')
        AND a.privilege_type='EXECUTE' AND NOT a.is_grantable) AS present""", (epoch.NEUTRAL_LOCK,)).fetchone()['present']
    if not extra:
        raise ValueError(ERROR)
    for row, expected in rows.values():
        if (row is None or row['prosrc'] != expected or row['rolname'] != 'aos_capacity_publication_owner'
            or row['prosecdef'] or row['proisstrict'] or row['proconfig'] != ['search_path=pg_catalog']
            or row['provolatile'] != 'v' or row['proparallel'] != 'u' or row['prokind'] != 'f'
            or row['proretset'] or row['prorettype'] != 2278 or row['pronargs'] != 0 or row['args'] != ''
            or row['pronargdefaults'] != 0 or row['provariadic'] != 0 or row['proleakproof']
            or row['prosupport'] != 0 or row['lanname'] != 'plpgsql'):
            raise ValueError(ERROR)
        acl = conn.execute("""SELECT a.grantee::regrole::text AS grantee,a.grantor::regrole::text AS grantor,
            a.privilege_type,a.is_grantable FROM pg_proc p,
            LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s""", (row['oid'],)).fetchall()
        if acl != [dict(grantee='aos_capacity_publication_owner',grantor='aos_capacity_publication_owner',
                        privilege_type='EXECUTE',is_grantable=False)]:
            raise ValueError(ERROR)
    return True
