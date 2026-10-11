"""Independent source/rehearsal data and restored metadata comparison."""
import hashlib
import json
import prepare_volume as P

SOURCE = 'qyh-restored-pg-20261011'
TARGET = 'qyh-stage-transport-rehearsal-r2-20261011'
LOGIN = 'qyh_stage_transport_rehearsal_20261011'

QUERIES = {
    'retainedRoles': """SELECT rolname,rolcanlogin,rolsuper,rolbypassrls,rolinherit,
        rolcreaterole,rolcreatedb,rolreplication,rolconnlimit,rolvaliduntil,
        md5(coalesce(rolconfig::text,'')) AS configuration_hash FROM pg_roles
        WHERE rolname NOT LIKE 'pg_%' AND rolname<>'qyh_stage_transport_rehearsal_20261011'
        ORDER BY rolname""",
    'retainedMemberships': """SELECT r.rolname AS role,u.rolname AS member,g.rolname AS grantor,
        m.admin_option,m.inherit_option,m.set_option FROM pg_auth_members m
        JOIN pg_roles r ON r.oid=m.roleid JOIN pg_roles u ON u.oid=m.member
        JOIN pg_roles g ON g.oid=m.grantor WHERE r.rolname NOT LIKE 'pg_%'
        AND u.rolname<>'qyh_stage_transport_rehearsal_20261011'
        ORDER BY r.rolname,u.rolname,g.rolname""",
    'relationOwnerAndRls': """SELECT n.nspname,c.relname,c.relkind,
        pg_get_userbyid(c.relowner) AS owner,c.relrowsecurity,c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema')
        AND n.nspname NOT LIKE 'pg_toast%' ORDER BY n.nspname,c.relname""",
    'relationGrants': """SELECT n.nspname,c.relname,pg_get_userbyid(a.grantor) AS grantor,
        CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,
        a.privilege_type,a.is_grantable FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(c.relacl) a
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'
        ORDER BY n.nspname,c.relname,grantor,grantee,a.privilege_type,a.is_grantable""",
    'columnGrants': """SELECT n.nspname,c.relname,col.attname,
        pg_get_userbyid(a.grantor) AS grantor,
        CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,
        a.privilege_type,a.is_grantable FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute col ON col.attrelid=c.oid CROSS JOIN LATERAL aclexplode(col.attacl) a
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'
        ORDER BY n.nspname,c.relname,col.attname,grantor,grantee,a.privilege_type,a.is_grantable""",
    'functions': """SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,
        pg_get_userbyid(p.proowner) AS owner,p.prosecdef,
        md5(pg_get_functiondef(p.oid)) AS definition_hash
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND p.prokind<>'a'
        ORDER BY n.nspname,p.proname,arguments""",
}


def metadata(container):
    output = {}
    for name, query in QUERIES.items():
        rows = json.loads(P.M.psql(container,'aos_meta_head',
            'BEGIN READ ONLY; SELECT coalesce(json_agg(x),\'[]\') FROM ('+query+') x; COMMIT;'))
        output[name] = rows
    return output


if __name__ == '__main__':
    output = P.R / 'stage-transport-r2-independent-readback.json'
    assert not output.exists(), 'Existing evidence: reconcile only'
    terminal = json.loads((P.R/'stage-transport-r2-terminal.json').read_text())
    assert terminal['outcome'] == 'FULL_CLONE_STAGE_SCRAM_TRANSPORT_VERIFIED'
    source, restored = metadata(SOURCE), metadata(TARGET)
    assert source == restored, 'Metadata restore differs; no formal promotion'
    source_data, target_data = P.M.fingerprint(SOURCE), P.M.fingerprint(TARGET)
    assert source_data == target_data and len(source_data) == 647
    result = {'source': SOURCE,'rehearsal':TARGET,'sourceVolume':P.VOLUME,
        'metadataEquality': {key: {'count': len(value),'exact': True,
            'sha256':hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()}
            for key,value in source.items()},
        'businessTableFingerprintExact':True,'tables':647,
        'actualPasswordLoginAndDenialsVerifiedBy': 'stage-transport-r2-terminal.json',
        'historicalPasswordsRestored':False,'currentRoleOrSourcePermissionsChanged':False,
        'formalOwnerOrPublisherProven':False,'fullRestorationAccepted':False}
    with output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'tables':647,'metadata':{k:len(v) for k,v in source.items()},'exact':True}))
