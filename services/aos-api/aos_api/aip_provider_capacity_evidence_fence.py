"""Hold neutral Evidence epochs through the caller's Source review/issuance commit."""
import hashlib

import psycopg

from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.aip_production_contract_store import AipProductionContractStore,ProductionContractError
from aos_api.tenant_scope import TenantScope

OWNER='aos_capacity_evidence_epoch_owner'
TABLE='public.aip_capacity_evidence_epoch'
FUNCTIONS={
    'lock':'b9e0dfa8cd25d0570e61c14fc9d9cb86652891fc3845e8e153935dafa53d42ce',
    'touch':'4d8d80c5f22143cb22ccf9a769c3878c4382a9f8cff4b5bde52cc47a46c5fd0e',
    'bump':'74ac1434ed7069a03ce4c9d90a459527d5a18cc974ba98c55c67b9b5ae12ecef',
    'issuer_lock':'763f808a880573c3f6cd372beb76347b68e93fa864f3a620b6a0c7764bb13c58',
}


class CapacityEvidenceFenceBlocked(ValueError):
    pass


def _require_boundary(conn):
    role=conn.execute('SELECT * FROM pg_roles WHERE rolname=%s',(OWNER,)).fetchone()
    if (not role or any(role[k] for k in ('rolcanlogin','rolinherit','rolsuper','rolcreatedb',
        'rolcreaterole','rolreplication','rolbypassrls')) or conn.execute(
        'SELECT 1 FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(OWNER,OWNER)).fetchone()):
        raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_OWNER_DRIFTED')
    table=conn.execute('SELECT relowner=%s::regrole AS owner,relrowsecurity,relforcerowsecurity,relkind '
        'FROM pg_class WHERE oid=%s::regclass',(OWNER,TABLE)).fetchone()
    if (not table or not table['owner'] or table['relkind']!='r' or not table['relrowsecurity'] or not table['relforcerowsecurity']
        or conn.execute('SELECT 1 FROM pg_class c,LATERAL aclexplode(coalesce(c.relacl,acldefault(\'r\',c.relowner))) a '
            'WHERE c.oid=%s::regclass AND a.grantee<>%s::regrole',(TABLE,OWNER)).fetchone()
        or conn.execute('SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a '
            'WHERE c.attrelid=%s::regclass AND a.grantee<>%s::regrole',(TABLE,OWNER)).fetchone()):
        raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_TABLE_DRIFTED')
    policies=conn.execute('SELECT polname,polcmd,polpermissive,polroles,pg_get_expr(polqual,polrelid) AS using_expr,'
        'pg_get_expr(polwithcheck,polrelid) AS check_expr FROM pg_policy WHERE polrelid=%s::regclass',(TABLE,)).fetchall()
    expected="((org_id = NULLIF(current_setting('aos.org_id'::text, true), ''::text)) AND (project_id = NULLIF(current_setting('aos.project_id'::text, true), ''::text)))"
    if (len(policies)!=1 or policies[0]['polname']!='capacity_evidence_epoch_scope' or policies[0]['polcmd']!='*'
        or policies[0]['polpermissive'] is not True or policies[0]['polroles']!=[role['oid']]
        or policies[0]['using_expr']!=expected or policies[0]['check_expr']!=expected):
        raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_RLS_POLICY_DRIFTED')
    ids=[]
    for name,digest in FUNCTIONS.items():
        reader=name in ('lock','issuer_lock')
        signature=f"public.aos_capacity_evidence_epoch_{name}({'text,text,text' if reader else ''})"
        row=conn.execute('SELECT oid,proowner=%s::regrole AS owner,prosecdef,proconfig,prosrc,prorettype,proargtypes::text AS args '
            'FROM pg_proc WHERE oid=to_regprocedure(%s)',(OWNER,signature)).fetchone()
        if (not row or not row['owner'] or not row['prosecdef'] or row['proconfig']!=['search_path=pg_catalog']
            or row['prorettype']!=(20 if reader else 2279) or row['args']!=('25 25 25' if reader else '')
            or hashlib.sha256(row['prosrc'].encode()).hexdigest()!=digest):
            raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_FUNCTION_DRIFTED')
        ids.append(row['oid'])
        caller='aos_runtime' if name=='lock' else 'aos_provider_capacity_issuer'
        allowed=[OWNER]+([caller] if reader else [])
        grants=conn.execute('SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_proc p,'
            "LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s",(row['oid'],)).fetchall()
        allowed_oids=conn.execute('SELECT oid,rolname FROM pg_roles WHERE rolname=ANY(%s)',(allowed,)).fetchall()
        by_oid={r['oid']:r['rolname'] for r in allowed_oids}
        if (any(g['grantee'] not in by_oid or g['privilege_type']!='EXECUTE'
                or (by_oid.get(g['grantee'])!='aos_capacity_evidence_epoch_owner' and g['is_grantable']) for g in grants)
            or (reader and not any(by_oid.get(g['grantee'])==caller for g in grants))):
            raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_FUNCTION_ACL_DRIFTED')
    triggers=conn.execute("SELECT tgname,tgfoid,tgenabled,tgtype,tgattr::text AS attrs,tgqual,tgargs FROM pg_trigger "
        "WHERE tgrelid='public.aip_evidence_bundle_revoke_event'::regclass AND tgname=ANY(%s)",
        (['capacity_evidence_epoch_touch_a0v149','capacity_evidence_epoch_bump_a0v149'],)).fetchall()
    expected={'capacity_evidence_epoch_touch_a0v149':(ids[1],7),'capacity_evidence_epoch_bump_a0v149':(ids[2],5)}
    if (len(triggers)!=2 or any((t['tgfoid'],t['tgtype'])!=expected[t['tgname']] or t['tgenabled']!='O'
        or t['attrs']!='' or t['tgqual'] is not None or bytes(t['tgargs'])!=b'' for t in triggers)):
        raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_TRIGGER_DRIFTED')
    extra=conn.execute("""SELECT
      EXISTS(SELECT 1 FROM pg_class c,pg_class target WHERE target.oid=%s::regclass AND c.relowner=%s::regrole
          AND c.oid<>target.oid AND c.oid<>target.reltoastrelid
          AND NOT EXISTS(SELECT 1 FROM pg_index i WHERE i.indexrelid=c.oid AND i.indrelid IN(target.oid,target.reltoastrelid)))
      OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner=%s::regrole AND NOT (oid=ANY(%s::oid[])))
      OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner=%s::regrole)
      OR EXISTS(SELECT 1 FROM pg_database WHERE datdba=%s::regrole)
      OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee=%s::regrole AND c.oid<>%s::regclass)
      OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee=%s::regrole AND c.attrelid<>%s::regclass)
      OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee=%s::regrole AND NOT(p.oid=ANY(%s::oid[])))
      OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee=%s::regrole
          AND (n.nspname<>'public' OR a.privilege_type<>'USAGE' OR a.is_grantable)) AS extra""",
      (TABLE,OWNER,OWNER,ids,OWNER,OWNER,OWNER,TABLE,OWNER,TABLE,OWNER,ids,OWNER)).fetchone()['extra']
    if extra:raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_OWNER_EXTRA_PRIVILEGE')


def lock_capacity_evidence_refs(conn,scope,refs):
    if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
        or type(refs) not in (list,tuple) or not refs or any(type(r) is not FormalExactRef for r in refs)):
        raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_NATIVE_CONTEXT_REQUIRED')
    if conn.autocommit or conn.info.transaction_status!=psycopg.pq.TransactionStatus.INTRANS:
        raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_CALLER_TRANSACTION_REQUIRED')
    try:
        refs=[FormalExactRef.model_validate(r.model_dump(mode='python',by_alias=True)) for r in refs]
        if any(r.asset_type!='EvidenceBundleRevision' or not 1<=len(r.asset_id)<=200 or r.asset_id!=r.asset_id.strip() for r in refs):
            raise ValueError('exact Evidence required')
        identity=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id,current_setting('session_replication_role') AS replication,"
            "current_setting('transaction_read_only') AS read_only,current_setting('transaction_isolation') AS isolation").fetchone()
        if ((identity['org_id'],identity['project_id'],identity['replication'])!=(*scope.key,'origin')
            or identity['read_only']!='off' or identity['isolation'] not in {'read committed','serializable'}):
            raise ValueError('native tenant runtime required')
        if identity['role']=='aos_provider_capacity_issuer':
            from aos_api.aip_provider_capacity_formal_boundary import require_capacity_issuer_identity
            require_capacity_issuer_identity(conn,scope)
            function='public.aos_capacity_evidence_epoch_issuer_lock'
        elif identity['role']=='aos_runtime':function='public.aos_capacity_evidence_epoch_lock'
        else:raise ValueError('native tenant caller required')
        _require_boundary(conn)
        epochs={}
        for bundle_id in sorted({r.asset_id for r in refs}):
            epochs[bundle_id]=conn.execute(f'SELECT {function}(%s,%s,%s) AS epoch',
                (*scope.key,bundle_id)).fetchone()['epoch']
        store=AipProductionContractStore()
        for ref in refs:
            item=store.get_evidence_bundle(scope,ref.asset_id,ref.revision,conn=conn)
            if item.content_hash!=ref.content_hash or item.lifecycle.value!='frozen' or item.revoked:
                raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_CURRENT_EXACT_REQUIRED')
        return epochs
    except (TypeError,ValueError,ProductionContractError,psycopg.Error) as exc:
        if isinstance(exc,CapacityEvidenceFenceBlocked):raise
        raise CapacityEvidenceFenceBlocked('CAPACITY_EVIDENCE_BOUNDARY_OR_CURRENTNESS_REQUIRED') from exc
