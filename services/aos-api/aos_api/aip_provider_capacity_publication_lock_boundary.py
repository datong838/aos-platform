"""Exact original epoch access for publication, never Source authorization."""
import hashlib

from aos_api.aip_provider_capacity_publication_registry import OWNER
from aos_api.aip_provider_capacity_publication_transaction import require_original_fact_boundary
from aos_api.aip_provider_capacity_evidence_fence import FUNCTIONS
from aos_api.aip_capacity_withdrawal_fence import HASHES

EPOCH_FUNCTIONS = {
    'public.aos_capacity_evidence_epoch_issuer_lock(text,text,text)':
        ('aos_capacity_evidence_epoch_owner', FUNCTIONS['issuer_lock']),
    'public.aos_capacity_withdrawal_epoch_lock(text,text,text)':
        ('aos_capacity_withdrawal_epoch_owner', HASHES['lock']),
}


class CapacityPublicationLockBlocked(ValueError):
    pass


def install_publication_epoch_locks(execute):
    """Add only the original pair; do not replace bodies or old grants."""
    execute(f"""DO $$ DECLARE r record; BEGIN
      SELECT * INTO r FROM pg_roles WHERE rolname='{OWNER}';
      IF NOT FOUND OR r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
        OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls
        OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid) THEN
        RAISE EXCEPTION 'CAPACITY_PUBLICATION_LOCK_OWNER_REQUIRED' USING ERRCODE='42501';
      END IF;
    END $$""")
    for signature, (neutral_owner, digest) in EPOCH_FUNCTIONS.items():
        execute(f"""DO $$ BEGIN
          IF NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
            JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=to_regprocedure('{signature}')
            AND r.rolname='{neutral_owner}' AND l.lanname='plpgsql' AND p.prosecdef
            AND p.proconfig=ARRAY['search_path=pg_catalog'] AND p.prorettype=20
            AND p.proargtypes='25 25 25'::oidvector
            AND encode(sha256(convert_to(p.prosrc,'UTF8')),'hex')='{digest}') THEN
            RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_LOCK_REQUIRED' USING ERRCODE='42501';
          END IF;
        END $$""")
        execute(f'GRANT EXECUTE ON FUNCTION {signature} TO {OWNER}')


def require_publication_lock_boundary(conn):
    """Require the complete pair and original fact/identity boundaries."""
    def deny():
        raise CapacityPublicationLockBlocked('CAPACITY_PUBLICATION_ORIGINAL_LOCK_BOUNDARY_DRIFTED')
    try:
        require_original_fact_boundary(conn)
    except ValueError as error:
        raise CapacityPublicationLockBlocked('CAPACITY_PUBLICATION_LOCK_OWNER_DRIFTED') from error
    role_oid = conn.execute('SELECT oid FROM pg_roles WHERE rolname=%s', (OWNER,)).fetchone()['oid']
    ids = []
    for signature, (neutral_owner, digest) in EPOCH_FUNCTIONS.items():
        row = conn.execute('SELECT p.oid,r.rolname,l.lanname,p.prosecdef,p.proconfig,p.prorettype,'
            'p.proargtypes::text AS args,p.prosrc FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner '
            'JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=to_regprocedure(%s)', (signature,)).fetchone()
        if (not row or row['rolname']!=neutral_owner or row['lanname']!='plpgsql'
            or not row['prosecdef'] or row['proconfig']!=['search_path=pg_catalog']
            or row['prorettype']!=20 or row['args']!='25 25 25'
            or hashlib.sha256(row['prosrc'].encode()).hexdigest()!=digest):
            deny()
        ids.append(row['oid'])
        allowed={neutral_owner,OWNER,'aos_provider_capacity_issuer'}
        if neutral_owner=='aos_capacity_withdrawal_epoch_owner':
            allowed.add('aos_runtime')
        acl=conn.execute("SELECT coalesce(r.rolname,'PUBLIC') AS role,a.privilege_type,a.is_grantable "
            "FROM pg_proc p,LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a "
            'LEFT JOIN pg_roles r ON r.oid=a.grantee WHERE p.oid=%s', (row['oid'],)).fetchall()
        if ({r['role'] for r in acl}!=allowed
            or any(r['privilege_type']!='EXECUTE' or (r['is_grantable']
                and not (r['role']==neutral_owner=='aos_capacity_evidence_epoch_owner')) for r in acl)):
            deny()
    grants = conn.execute('SELECT p.oid,a.privilege_type,a.is_grantable FROM pg_proc p,'
        'LATERAL aclexplode(p.proacl) a WHERE p.pronamespace=\'public\'::regnamespace '
        'AND p.proowner<>%s AND a.grantee=%s', (role_oid,role_oid)).fetchall()
    if (len(grants)!=2 or {r['oid'] for r in grants}!=set(ids)
        or any(r['privilege_type']!='EXECUTE' or r['is_grantable'] for r in grants)):
        deny()
    # PUBLIC remains effective for NOINHERIT. Future Source must independently audit Owner-owned entrypoints;
    # this bridge admits no external helper.
    effective = conn.execute('SELECT oid FROM pg_proc WHERE pronamespace=\'public\'::regnamespace '
        'AND proowner<>%s AND prosecdef AND has_function_privilege(%s,oid,\'EXECUTE\')',
        (role_oid,OWNER)).fetchall()
    if {r['oid'] for r in effective}!=set(ids):
        deny()


def audited_publication_epoch_caller(conn):
    """Legacy ACLs remain valid without grants; a partial pair is drift."""
    present = conn.execute('SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a '
        'WHERE a.grantee=to_regrole(%s)::oid AND p.oid IN '
        '(SELECT to_regprocedure(sig)::oid FROM unnest(%s::text[]) sig) LIMIT 1',
        (OWNER,list(EPOCH_FUNCTIONS))).fetchone()
    if not present:
        return None
    require_publication_lock_boundary(conn)
    return OWNER
